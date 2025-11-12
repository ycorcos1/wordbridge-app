"""Data access layer for WordBridge without external ORM dependencies."""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, Optional, Sequence
from urllib.parse import urlparse

import psycopg
from flask_login import UserMixin
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

from config.settings import get_settings

_connection: Optional[object] = None
_backend: Optional[str] = None  # "sqlite" or "postgres"

_BASELINE_FILES: Dict[int, str] = {
    6: "6th_grade.json",
    7: "7th_grade.json",
    8: "8th_grade.json",
}


class User(UserMixin):
    """Flask-Login compatible user wrapper."""

    def __init__(
        self,
        *,
        id: int,
        email: str,
        username: str,
        password_hash: str,
        role: str,
        name: str,
        created_at: datetime.datetime,
    ) -> None:
        self.id = id
        self.email = email
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.name = name
        self.created_at = created_at

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User id={self.id} role={self.role} username={self.username!r}>"


def _resolve_default_sqlite_path() -> str:
    root_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(root_dir, "wordbridge_dev.sqlite")


def _normalize_sqlite_path(database_url: str) -> str:
    parsed = urlparse(database_url)
    path = parsed.path or ""
    if path.startswith("/"):
        path = path[1:]
    if path in {"", ":memory:"}:
        return ":memory:"
    if parsed.netloc:
        path = os.path.join(parsed.netloc, path)
    return path or _resolve_default_sqlite_path()


def get_connection():
    """Return a singleton database connection."""
    global _connection, _backend
    if _connection is not None:
        return _connection

    settings = get_settings()
    database_url = settings.DATABASE_URL or f"sqlite:///{_resolve_default_sqlite_path()}"

    # Normalize database URL - handle postgres:// and postgresql://
    if database_url and not database_url.startswith("sqlite"):
        # Ensure it's treated as PostgreSQL
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

    if database_url and database_url.startswith("sqlite"):
        db_path = _normalize_sqlite_path(database_url)
        conn = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _connection = conn
        _backend = "sqlite"
    else:
        # PostgreSQL connection
        conn = psycopg.connect(database_url, row_factory=dict_row)
        _connection = conn
        _backend = "postgres"

    return _connection


def reset_engine() -> None:
    """Reset the current database connection (used in tests)."""
    global _connection, _backend
    if _connection is not None:
        _connection.close()
    _connection = None
    _backend = None


def init_db() -> None:
    """Create the users table if it does not already exist."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "postgres":
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    username VARCHAR(64) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(16) NOT NULL CHECK (role IN ('educator', 'student')),
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS student_profiles (
                    student_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    educator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    grade_level INTEGER NOT NULL CHECK (grade_level IN (6, 7, 8)),
                    class_number INTEGER NOT NULL,
                    vocabulary_level INTEGER NOT NULL DEFAULT 0,
                    last_analyzed_at TIMESTAMP NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS baseline_words (
                    id SERIAL PRIMARY KEY,
                    word VARCHAR(255) NOT NULL,
                    definition TEXT NOT NULL,
                    difficulty INTEGER NOT NULL,
                    grade_level INTEGER NOT NULL CHECK (grade_level IN (6, 7, 8))
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_baseline_words_grade
                ON baseline_words (grade_level);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_profiles_educator
                ON student_profiles (educator_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_profiles_class
                ON student_profiles (educator_id, grade_level, class_number);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id SERIAL PRIMARY KEY,
                    educator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    file_path TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    status VARCHAR(16) NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
                    processed_at TIMESTAMP NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_uploads_student
                ON uploads (student_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_uploads_status
                ON uploads (status);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendations (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    upload_id INTEGER NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
                    word VARCHAR(255) NOT NULL,
                    definition TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    difficulty_score INTEGER NOT NULL CHECK (difficulty_score BETWEEN 1 AND 10),
                    example_sentence TEXT NOT NULL,
                    status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
                    pinned BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recommendations_student
                ON recommendations (student_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recommendations_upload
                ON recommendations (upload_id);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS student_progress (
                    student_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    xp INTEGER NOT NULL DEFAULT 0,
                    streak_count INTEGER NOT NULL DEFAULT 0,
                    last_quiz_at TIMESTAMP NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS badges (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    badge_type VARCHAR(32) NOT NULL CHECK (badge_type IN ('10_words', '50_words', '100_words')),
                    earned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_badges_student
                ON badges (student_id);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS word_mastery (
                    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    word_id INTEGER NOT NULL REFERENCES recommendations(id) ON DELETE CASCADE,
                    mastery_stage VARCHAR(32) NOT NULL CHECK (mastery_stage IN ('practicing', 'nearly_mastered', 'mastered')),
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    last_practiced_at TIMESTAMP NULL,
                    PRIMARY KEY (student_id, word_id)
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_word_mastery_student
                ON word_mastery (student_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_word_mastery_word
                ON word_mastery (word_id);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    word_id INTEGER NOT NULL REFERENCES recommendations(id) ON DELETE CASCADE,
                    correct BOOLEAN NOT NULL,
                    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student
                ON quiz_attempts (student_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_quiz_attempts_attempted
                ON quiz_attempts (attempted_at);
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('educator', 'student')),
                    name TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS student_profiles (
                    student_id INTEGER PRIMARY KEY,
                    educator_id INTEGER NOT NULL,
                    grade_level INTEGER NOT NULL CHECK (grade_level IN (6, 7, 8)),
                    class_number INTEGER NOT NULL,
                    vocabulary_level INTEGER NOT NULL DEFAULT 0,
                    last_analyzed_at TIMESTAMP NULL,
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(educator_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS baseline_words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    difficulty INTEGER NOT NULL,
                    grade_level INTEGER NOT NULL CHECK (grade_level IN (6, 7, 8))
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_baseline_words_grade
                ON baseline_words (grade_level);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_profiles_educator
                ON student_profiles (educator_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_profiles_class
                ON student_profiles (educator_id, grade_level, class_number);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    educator_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
                    processed_at TIMESTAMP NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(educator_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_uploads_student
                ON uploads (student_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_uploads_status
                ON uploads (status);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    upload_id INTEGER NOT NULL,
                    word TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    difficulty_score INTEGER NOT NULL,
                    example_sentence TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
                    pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(upload_id) REFERENCES uploads(id) ON DELETE CASCADE
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recommendations_student
                ON recommendations (student_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recommendations_upload
                ON recommendations (upload_id);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS student_progress (
                    student_id INTEGER PRIMARY KEY,
                    xp INTEGER NOT NULL DEFAULT 0,
                    streak_count INTEGER NOT NULL DEFAULT 0,
                    last_quiz_at TIMESTAMP NULL,
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS badges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    badge_type TEXT NOT NULL CHECK (badge_type IN ('10_words', '50_words', '100_words')),
                    earned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_badges_student
                ON badges (student_id);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS word_mastery (
                    student_id INTEGER NOT NULL,
                    word_id INTEGER NOT NULL,
                    mastery_stage TEXT NOT NULL CHECK (mastery_stage IN ('practicing', 'nearly_mastered', 'mastered')),
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    last_practiced_at TIMESTAMP NULL,
                    PRIMARY KEY(student_id, word_id),
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(word_id) REFERENCES recommendations(id) ON DELETE CASCADE
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_word_mastery_student
                ON word_mastery (student_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_word_mastery_word
                ON word_mastery (word_id);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    word_id INTEGER NOT NULL,
                    correct INTEGER NOT NULL,
                    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(word_id) REFERENCES recommendations(id) ON DELETE CASCADE
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student
                ON quiz_attempts (student_id);
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_quiz_attempts_attempted
                ON quiz_attempts (attempted_at);
                """
            )
        conn.commit()
    finally:
        cur.close()


def _row_to_user(row: Optional[dict]) -> Optional[User]:
    if not row:
        return None

    created_at = row.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.datetime.fromisoformat(created_at)

    return User(
        id=row["id"],
        email=row["email"],
        username=row["username"],
        password_hash=row["password_hash"],
        role=row["role"],
        name=row["name"],
        created_at=created_at,
    )


def _execute_fetchone(query: str, params: tuple) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            query = query.replace("%s", "?")
        cur.execute(query, params)
        row = cur.fetchone()
        if row is None:
            return None
        if _backend == "sqlite":
            row = dict(row)
        return row
    finally:
        cur.close()


def get_user_by_id(user_id: int) -> Optional[User]:
    row = _execute_fetchone(
        "SELECT * FROM users WHERE id = %s",
        (user_id,),
    )
    return _row_to_user(row)


def get_user_by_identifier(identifier: str) -> Optional[User]:
    if not identifier:
        return None

    row = _execute_fetchone(
        "SELECT * FROM users WHERE email = %s OR username = %s",
        (identifier, identifier),
    )
    return _row_to_user(row)


def create_user(
    *,
    name: str,
    email: str,
    username: str,
    password_hash: str,
    role: str,
) -> User:
    normalized_role = role.lower()
    if normalized_role not in {"educator", "student"}:
        raise ValueError("Role must be 'educator' or 'student'.")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "postgres":
            cur.execute(
                """
                INSERT INTO users (name, email, username, password_hash, role)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (name, email, username, password_hash, normalized_role),
            )
            new_id = cur.fetchone()["id"]
        else:
            cur.execute(
                """
                INSERT INTO users (name, email, username, password_hash, role)
                VALUES (?, ?, ?, ?, ?);
                """,
                (name, email, username, password_hash, normalized_role),
            )
            new_id = cur.lastrowid
        conn.commit()
    except (sqlite3.IntegrityError, pg_errors.UniqueViolation) as exc:
        conn.rollback()
        raise ValueError("Email or username already in use.") from exc
    finally:
        cur.close()

    user = get_user_by_id(new_id)
    if user is None:
        raise RuntimeError("Failed to retrieve created user.")
    return user


def delete_user(user_id: int) -> None:
    """Delete a user and all their associated data via CASCADE."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute("DELETE FROM users WHERE id = ?;", (user_id,))
        else:
            cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
        conn.commit()
    finally:
        cur.close()


def _default_baseline_dir() -> Path:
    root_dir = os.path.dirname(os.path.dirname(__file__))
    return Path(root_dir) / "data" / "baseline"


def _row_to_scalar(row) -> int:
    if row is None:
        return 0
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def _fallback_baseline_words(grade_level: int) -> list[dict[str, object]]:
    samples: Dict[int, list[dict[str, object]]] = {
        6: [
            {
                "word": "analyze",
                "definition": "Examine something carefully to understand it.",
                "difficulty": 3,
            },
            {
                "word": "context",
                "definition": "The surrounding information that helps explain meaning.",
                "difficulty": 3,
            },
        ],
        7: [
            {
                "word": "evaluate",
                "definition": "Judge or determine the value of something.",
                "difficulty": 4,
            },
            {
                "word": "interpret",
                "definition": "Explain the meaning of information or actions.",
                "difficulty": 4,
            },
        ],
        8: [
            {
                "word": "synthesize",
                "definition": "Combine parts to form a whole.",
                "difficulty": 6,
            },
            {
                "word": "nuance",
                "definition": "A subtle difference in meaning or expression.",
                "difficulty": 5,
            },
        ],
    }
    entries = samples.get(grade_level, [])
    for entry in entries:
        entry.setdefault("grade_level", grade_level)
    return entries


def ensure_baseline_words_loaded(
    baseline_dir: str | os.PathLike[str] | None = None,
) -> None:
    """Load baseline vocabulary data if the table is empty."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM baseline_words;")
        existing_row = cur.fetchone()
        if _row_to_scalar(existing_row) > 0:
            return

        base_dir = Path(baseline_dir) if baseline_dir else _default_baseline_dir()
        records: list[tuple[str, str, int, int]] = []

        for grade_level, filename in _BASELINE_FILES.items():
            file_path = base_dir / filename
            if file_path.exists():
                try:
                    with file_path.open("r", encoding="utf-8") as handle:
                        words = json.load(handle)
                except (json.JSONDecodeError, OSError):
                    words = _fallback_baseline_words(grade_level)
            else:
                words = _fallback_baseline_words(grade_level)

            for entry in words:
                word = (entry.get("word") or "").strip()
                definition = (entry.get("definition") or "").strip()
                if not word or not definition:
                    continue
                difficulty = entry.get("difficulty", 3)
                try:
                    difficulty_int = int(difficulty)
                except (TypeError, ValueError):
                    difficulty_int = 3
                records.append(
                    (
                        word,
                        definition,
                        difficulty_int,
                        int(entry.get("grade_level", grade_level)),
                    )
                )

        if not records:
            return

        if _backend == "sqlite":
            cur.executemany(
                """
                INSERT INTO baseline_words (word, definition, difficulty, grade_level)
                VALUES (?, ?, ?, ?)
                """,
                records,
            )
        else:
            cur.executemany(
                """
                INSERT INTO baseline_words (word, definition, difficulty, grade_level)
                VALUES (%s, %s, %s, %s)
                """,
                records,
            )
        conn.commit()
    finally:
        cur.close()


def count_baseline_words_for_grade(grade_level: int) -> int:
    """Return the number of baseline words present for a grade level."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                "SELECT COUNT(*) FROM baseline_words WHERE grade_level = ?;",
                (grade_level,),
            )
        else:
            cur.execute(
                "SELECT COUNT(*) FROM baseline_words WHERE grade_level = %s;",
                (grade_level,),
            )
        row = cur.fetchone()
        return int(_row_to_scalar(row))
    finally:
        cur.close()


def create_student_profile(
    *,
    student_id: int,
    educator_id: int,
    grade_level: int,
    class_number: int,
    vocabulary_level: int = 0,
) -> None:
    """Create a student profile entry linked to an educator."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                INSERT INTO student_profiles (
                    student_id,
                    educator_id,
                    grade_level,
                    class_number,
                    vocabulary_level
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (student_id, educator_id, grade_level, class_number, vocabulary_level),
            )
        else:
            cur.execute(
                """
                INSERT INTO student_profiles (
                    student_id,
                    educator_id,
                    grade_level,
                    class_number,
                    vocabulary_level
                ) VALUES (%s, %s, %s, %s, %s);
                """,
                (student_id, educator_id, grade_level, class_number, vocabulary_level),
            )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError("Student profile already exists.") from exc
    except pg_errors.UniqueViolation as exc:
        conn.rollback()
        raise ValueError("Student profile already exists.") from exc
    finally:
        cur.close()


def update_student_vocabulary_level(student_id: int, new_level: int) -> None:
    """Persist an updated vocabulary level for the given student."""
    try:
        level_value = int(new_level)
    except (TypeError, ValueError):
        level_value = 0
    level_value = max(0, level_value)

    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                UPDATE student_profiles
                SET vocabulary_level = ?
                WHERE student_id = ?;
                """,
                (level_value, student_id),
            )
        else:
            cur.execute(
                """
                UPDATE student_profiles
                SET vocabulary_level = %s
                WHERE student_id = %s;
                """,
                (level_value, student_id),
            )
        conn.commit()
    finally:
        cur.close()


def list_students_for_educator(educator_id: int) -> list[dict[str, object]]:
    """Return students belonging to an educator ordered by name."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT u.id, u.name, u.username, sp.grade_level, sp.class_number
                FROM student_profiles sp
                JOIN users u ON u.id = sp.student_id
                WHERE sp.educator_id = ?
                ORDER BY u.name ASC;
                """,
                (educator_id,),
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows] if rows else []
        cur.execute(
            """
            SELECT u.id, u.name, u.username, sp.grade_level, sp.class_number
            FROM student_profiles sp
            JOIN users u ON u.id = sp.student_id
            WHERE sp.educator_id = %s
            ORDER BY u.name ASC;
            """,
            (educator_id,),
        )
        rows = cur.fetchall()
        return rows or []
    finally:
        cur.close()


def count_students_for_educator(educator_id: int) -> int:
    """Return number of students linked to the educator."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM student_profiles
                WHERE educator_id = ?;
                """,
                (educator_id,),
            )
            row = cur.fetchone()
            return int(row["total"] if row else 0)
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM student_profiles
            WHERE educator_id = %s;
            """,
            (educator_id,),
        )
        row = cur.fetchone()
        return int(row["total"] if row else 0)
    finally:
        cur.close()


def count_pending_recommendations_for_educator(educator_id: int) -> int:
    """Return count of pending recommendations for the educator's students."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM recommendations r
                JOIN student_profiles sp ON sp.student_id = r.student_id
                WHERE sp.educator_id = ? AND r.status = 'pending';
                """,
                (educator_id,),
            )
            row = cur.fetchone()
            return int(row["total"] if row else 0)
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM recommendations r
            JOIN student_profiles sp ON sp.student_id = r.student_id
            WHERE sp.educator_id = %s AND r.status = 'pending';
            """,
            (educator_id,),
        )
        row = cur.fetchone()
        return int(row["total"] if row else 0)
    finally:
        cur.close()


def average_vocabulary_level_for_educator(educator_id: int) -> float:
    """Return average vocabulary level for the educator's students."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT AVG(vocabulary_level) AS avg_level
                FROM student_profiles
                WHERE educator_id = ?;
                """,
                (educator_id,),
            )
            row = cur.fetchone()
            value = row["avg_level"] if row else None
        else:
            cur.execute(
                """
                SELECT AVG(vocabulary_level) AS avg_level
                FROM student_profiles
                WHERE educator_id = %s;
                """,
                (educator_id,),
            )
            row = cur.fetchone()
            value = row["avg_level"] if row else None

        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    finally:
        cur.close()


def average_vocabulary_level_for_grade(educator_id: int, grade_level: int) -> float:
    """Return average vocabulary level for a specific grade."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT AVG(vocabulary_level) AS avg_level
                FROM student_profiles
                WHERE educator_id = ? AND grade_level = ?;
                """,
                (educator_id, grade_level),
            )
            row = cur.fetchone()
            value = row["avg_level"] if row else None
        else:
            cur.execute(
                """
                SELECT AVG(vocabulary_level) AS avg_level
                FROM student_profiles
                WHERE educator_id = %s AND grade_level = %s;
                """,
                (educator_id, grade_level),
            )
            row = cur.fetchone()
            value = row["avg_level"] if row else None

        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    finally:
        cur.close()


def average_vocabulary_level_for_class(
    educator_id: int, grade_level: int, class_number: int
) -> float:
    """Return average vocabulary level for a specific class."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT AVG(vocabulary_level) AS avg_level
                FROM student_profiles
                WHERE educator_id = ? AND grade_level = ? AND class_number = ?;
                """,
                (educator_id, grade_level, class_number),
            )
            row = cur.fetchone()
            value = row["avg_level"] if row else None
        else:
            cur.execute(
                """
                SELECT AVG(vocabulary_level) AS avg_level
                FROM student_profiles
                WHERE educator_id = %s AND grade_level = %s AND class_number = %s;
                """,
                (educator_id, grade_level, class_number),
            )
            row = cur.fetchone()
            value = row["avg_level"] if row else None

        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    finally:
        cur.close()


def list_students_with_stats_for_educator(
    educator_id: int,
) -> list[dict[str, object]]:
    """Return students for educator with pending count and last upload timestamp."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT
                    u.id AS student_id,
                    u.name,
                    sp.grade_level,
                    sp.class_number,
                    sp.vocabulary_level,
                    (
                        SELECT COUNT(*)
                        FROM recommendations r
                        WHERE r.student_id = sp.student_id AND r.status = 'pending'
                    ) AS pending_words,
                    (
                        SELECT COUNT(*)
                        FROM recommendations r
                        WHERE r.student_id = sp.student_id AND r.status = 'approved'
                    ) AS approved_words,
                    (
                        SELECT MAX(created_at)
                        FROM uploads up
                        WHERE up.student_id = sp.student_id
                    ) AS last_upload_at
                FROM student_profiles sp
                JOIN users u ON u.id = sp.student_id
                WHERE sp.educator_id = ?
                ORDER BY sp.grade_level ASC, sp.class_number ASC, u.name ASC;
                """,
                (educator_id,),
            )
            rows = cur.fetchall() or []
            return [
                {
                    "id": row["student_id"],
                    "name": row["name"],
                    "grade_level": row["grade_level"],
                    "class_number": row["class_number"],
                    "vocabulary_level": row["vocabulary_level"],
                    "pending_words": row["pending_words"] or 0,
                    "approved_words": row["approved_words"] or 0,
                    "last_upload_at": row["last_upload_at"],
                }
                for row in rows
            ]
        cur.execute(
            """
            SELECT
                u.id AS student_id,
                u.name,
                sp.grade_level,
                sp.class_number,
                sp.vocabulary_level,
                (
                    SELECT COUNT(*)
                    FROM recommendations r
                    WHERE r.student_id = sp.student_id AND r.status = 'pending'
                ) AS pending_words,
                (
                    SELECT COUNT(*)
                    FROM recommendations r
                    WHERE r.student_id = sp.student_id AND r.status = 'approved'
                ) AS approved_words,
                (
                    SELECT MAX(created_at)
                    FROM uploads up
                    WHERE up.student_id = sp.student_id
                ) AS last_upload_at
            FROM student_profiles sp
            JOIN users u ON u.id = sp.student_id
            WHERE sp.educator_id = %s
            ORDER BY sp.grade_level ASC, sp.class_number ASC, u.name ASC;
            """,
            (educator_id,),
        )
        rows = cur.fetchall() or []
        return [
            {
                "id": row["student_id"],
                "name": row["name"],
                "grade_level": row["grade_level"],
                "class_number": row["class_number"],
                "vocabulary_level": row["vocabulary_level"],
                "pending_words": row["pending_words"] or 0,
                "approved_words": row["approved_words"] or 0,
                "last_upload_at": row["last_upload_at"],
            }
            for row in rows
        ]
    finally:
        cur.close()


def list_students_with_stats_for_grade(
    educator_id: int, grade_level: int
) -> list[dict[str, object]]:
    """Return students for an educator filtered by grade."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT
                    u.id AS student_id,
                    u.name,
                    sp.grade_level,
                    sp.class_number,
                    sp.vocabulary_level,
                    (
                        SELECT COUNT(*)
                        FROM recommendations r
                        WHERE r.student_id = sp.student_id AND r.status = 'pending'
                    ) AS pending_words,
                    (
                        SELECT COUNT(*)
                        FROM recommendations r
                        WHERE r.student_id = sp.student_id AND r.status = 'approved'
                    ) AS approved_words,
                    (
                        SELECT MAX(created_at)
                        FROM uploads up
                        WHERE up.student_id = sp.student_id
                    ) AS last_upload_at
                FROM student_profiles sp
                JOIN users u ON u.id = sp.student_id
                WHERE sp.educator_id = ? AND sp.grade_level = ?
                ORDER BY sp.class_number ASC, u.name ASC;
                """,
                (educator_id, grade_level),
            )
            rows = cur.fetchall() or []
            return [
                {
                    "id": row["student_id"],
                    "name": row["name"],
                    "grade_level": row["grade_level"],
                    "class_number": row["class_number"],
                    "vocabulary_level": row["vocabulary_level"],
                    "pending_words": row["pending_words"] or 0,
                    "last_upload_at": row["last_upload_at"],
                }
                for row in rows
            ]
        cur.execute(
            """
            SELECT
                u.id AS student_id,
                u.name,
                sp.grade_level,
                sp.class_number,
                sp.vocabulary_level,
                (
                    SELECT COUNT(*)
                    FROM recommendations r
                    WHERE r.student_id = sp.student_id AND r.status = 'pending'
                ) AS pending_words,
                (
                    SELECT MAX(created_at)
                    FROM uploads up
                    WHERE up.student_id = sp.student_id
                ) AS last_upload_at
            FROM student_profiles sp
            JOIN users u ON u.id = sp.student_id
            WHERE sp.educator_id = %s AND sp.grade_level = %s
            ORDER BY sp.class_number ASC, u.name ASC;
            """,
            (educator_id, grade_level),
        )
        rows = cur.fetchall() or []
        return [
            {
                "id": row["student_id"],
                "name": row["name"],
                "grade_level": row["grade_level"],
                "class_number": row["class_number"],
                "vocabulary_level": row["vocabulary_level"],
                "pending_words": row["pending_words"] or 0,
                "approved_words": row["approved_words"] or 0,
                "last_upload_at": row["last_upload_at"],
            }
            for row in rows
        ]
    finally:
        cur.close()


def list_students_with_stats_for_class(
    educator_id: int, grade_level: int, class_number: int
) -> list[dict[str, object]]:
    """Return students for an educator filtered by grade and class."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT
                    u.id AS student_id,
                    u.name,
                    sp.grade_level,
                    sp.class_number,
                    sp.vocabulary_level,
                    (
                        SELECT COUNT(*)
                        FROM recommendations r
                        WHERE r.student_id = sp.student_id AND r.status = 'pending'
                    ) AS pending_words,
                    (
                        SELECT COUNT(*)
                        FROM recommendations r
                        WHERE r.student_id = sp.student_id AND r.status = 'approved'
                    ) AS approved_words,
                    (
                        SELECT MAX(created_at)
                        FROM uploads up
                        WHERE up.student_id = sp.student_id
                    ) AS last_upload_at
                FROM student_profiles sp
                JOIN users u ON u.id = sp.student_id
                WHERE sp.educator_id = ? AND sp.grade_level = ? AND sp.class_number = ?
                ORDER BY u.name ASC;
                """,
                (educator_id, grade_level, class_number),
            )
            rows = cur.fetchall() or []
            return [
                {
                    "id": row["student_id"],
                    "name": row["name"],
                    "grade_level": row["grade_level"],
                    "class_number": row["class_number"],
                    "vocabulary_level": row["vocabulary_level"],
                    "pending_words": row["pending_words"] or 0,
                    "approved_words": row["approved_words"] or 0,
                    "last_upload_at": row["last_upload_at"],
                }
                for row in rows
            ]
        cur.execute(
            """
            SELECT
                u.id AS student_id,
                u.name,
                sp.grade_level,
                sp.class_number,
                sp.vocabulary_level,
                (
                    SELECT COUNT(*)
                    FROM recommendations r
                    WHERE r.student_id = sp.student_id AND r.status = 'pending'
                ) AS pending_words,
                (
                    SELECT COUNT(*)
                    FROM recommendations r
                    WHERE r.student_id = sp.student_id AND r.status = 'approved'
                ) AS approved_words,
                (
                    SELECT MAX(created_at)
                    FROM uploads up
                    WHERE up.student_id = sp.student_id
                ) AS last_upload_at
            FROM student_profiles sp
            JOIN users u ON u.id = sp.student_id
            WHERE sp.educator_id = %s AND sp.grade_level = %s AND sp.class_number = %s
            ORDER BY u.name ASC;
            """,
            (educator_id, grade_level, class_number),
        )
        rows = cur.fetchall() or []
        return [
            {
                "id": row["student_id"],
                "name": row["name"],
                "grade_level": row["grade_level"],
                "class_number": row["class_number"],
                "vocabulary_level": row["vocabulary_level"],
                "pending_words": row["pending_words"] or 0,
                "approved_words": row["approved_words"] or 0,
                "last_upload_at": row["last_upload_at"],
            }
            for row in rows
        ]
    finally:
        cur.close()


def get_student_overview(
    educator_id: int, student_id: int
) -> Optional[dict[str, object]]:
    """Return student profile summary if it belongs to the educator."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT
                    u.id AS student_id,
                    u.name,
                    u.email,
                    sp.grade_level,
                    sp.class_number,
                    sp.vocabulary_level,
                    sp.last_analyzed_at,
                    (
                        SELECT COUNT(*)
                        FROM recommendations r
                        WHERE r.student_id = sp.student_id AND r.status = 'pending'
                    ) AS pending_words,
                    (
                        SELECT COUNT(*)
                        FROM recommendations r
                        WHERE r.student_id = sp.student_id AND r.status = 'approved'
                    ) AS approved_words,
                    (
                        SELECT COUNT(*)
                        FROM recommendations r
                        WHERE r.student_id = sp.student_id AND r.status = 'rejected'
                    ) AS rejected_words,
                    (
                        SELECT MAX(created_at)
                        FROM uploads up
                        WHERE up.student_id = sp.student_id
                    ) AS last_upload_at
                FROM student_profiles sp
                JOIN users u ON u.id = sp.student_id
                WHERE sp.educator_id = ? AND sp.student_id = ?;
                """,
                (educator_id, student_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "student_id": row["student_id"],
                "name": row["name"],
                "email": row["email"],
                "grade_level": row["grade_level"],
                "class_number": row["class_number"],
                "vocabulary_level": row["vocabulary_level"],
                "last_analyzed_at": row["last_analyzed_at"],
                "pending_words": row["pending_words"] or 0,
                "approved_words": row["approved_words"] or 0,
                "rejected_words": row["rejected_words"] or 0,
                "last_upload_at": row["last_upload_at"],
            }
        cur.execute(
            """
            SELECT
                u.id AS student_id,
                u.name,
                u.email,
                sp.grade_level,
                sp.class_number,
                sp.vocabulary_level,
                sp.last_analyzed_at,
                (
                    SELECT COUNT(*)
                    FROM recommendations r
                    WHERE r.student_id = sp.student_id AND r.status = 'pending'
                ) AS pending_words,
                (
                    SELECT COUNT(*)
                    FROM recommendations r
                    WHERE r.student_id = sp.student_id AND r.status = 'approved'
                ) AS approved_words,
                (
                    SELECT COUNT(*)
                    FROM recommendations r
                    WHERE r.student_id = sp.student_id AND r.status = 'rejected'
                ) AS rejected_words,
                (
                    SELECT MAX(created_at)
                    FROM uploads up
                    WHERE up.student_id = sp.student_id
                ) AS last_upload_at
            FROM student_profiles sp
            JOIN users u ON u.id = sp.student_id
            WHERE sp.educator_id = %s AND sp.student_id = %s;
            """,
            (educator_id, student_id),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "student_id": row["student_id"],
            "name": row["name"],
            "email": row["email"],
            "grade_level": row["grade_level"],
            "class_number": row["class_number"],
            "vocabulary_level": row["vocabulary_level"],
            "last_analyzed_at": row["last_analyzed_at"],
            "pending_words": row["pending_words"] or 0,
            "approved_words": row["approved_words"] or 0,
            "rejected_words": row["rejected_words"] or 0,
            "last_upload_at": row["last_upload_at"],
        }
    finally:
        cur.close()


def create_upload_record(
    *,
    educator_id: int,
    student_id: int,
    file_path: str,
    filename: str,
    status: str = "pending",
) -> int:
    """Insert a new upload row and return its identifier."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                INSERT INTO uploads (educator_id, student_id, file_path, filename, status)
                VALUES (?, ?, ?, ?, ?);
                """,
                (educator_id, student_id, file_path, filename, status),
            )
            new_id = cur.lastrowid
        else:
            cur.execute(
                """
                INSERT INTO uploads (educator_id, student_id, file_path, filename, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (educator_id, student_id, file_path, filename, status),
            )
            new_id = cur.fetchone()["id"]
        conn.commit()
        if new_id is None:
            raise RuntimeError("Upload was created but no identifier returned.")
        return int(new_id)
    finally:
        cur.close()


def update_upload_status(
    upload_id: int,
    status: str,
    processed_at: Optional[datetime.datetime] = None,
) -> None:
    """Update status (and optionally processed timestamp) for an upload."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                UPDATE uploads
                SET status = ?, processed_at = COALESCE(?, processed_at)
                WHERE id = ?;
                """,
                (status, processed_at, upload_id),
            )
        else:
            cur.execute(
                """
                UPDATE uploads
                SET status = %s, processed_at = COALESCE(%s, processed_at)
                WHERE id = %s;
                """,
                (status, processed_at, upload_id),
            )
        conn.commit()
    finally:
        cur.close()


def get_upload_status(upload_id: int) -> Optional[str]:
    """Return upload status string or None if not found."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                "SELECT status FROM uploads WHERE id = ?;",
                (upload_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            if isinstance(row, sqlite3.Row):
                return str(row["status"])
            return str(row[0])
        cur.execute(
            "SELECT status FROM uploads WHERE id = %s;",
            (upload_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return str(row["status"])
    finally:
        cur.close()


def get_upload_by_id(upload_id: int) -> Optional[dict[str, object]]:
    """Return upload metadata row or None."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                "SELECT * FROM uploads WHERE id = ?;",
                (upload_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        cur.execute(
            "SELECT * FROM uploads WHERE id = %s;",
            (upload_id,),
        )
        row = cur.fetchone()
        return row if row else None
    finally:
        cur.close()


def list_uploads_for_student(student_id: int) -> list[dict[str, object]]:
    """Return all uploads for a student, ordered by most recent first."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT id, educator_id, student_id, file_path, filename, status, 
                       processed_at, created_at
                FROM uploads
                WHERE student_id = ?
                ORDER BY created_at DESC;
                """,
                (student_id,),
            )
            rows = cur.fetchall() or []
            return [dict(row) for row in rows]
        cur.execute(
            """
            SELECT id, educator_id, student_id, file_path, filename, status, 
                   processed_at, created_at
            FROM uploads
            WHERE student_id = %s
            ORDER BY created_at DESC;
            """,
            (student_id,),
        )
        rows = cur.fetchall() or []
        return rows
    finally:
        cur.close()


def delete_upload(upload_id: int) -> None:
    """Delete an upload and its associated recommendations."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # First delete recommendations associated with this upload
        delete_recommendations_for_upload(upload_id)
        
        # Then delete the upload itself
        if _backend == "sqlite":
            cur.execute("DELETE FROM uploads WHERE id = ?;", (upload_id,))
        else:
            cur.execute("DELETE FROM uploads WHERE id = %s;", (upload_id,))
        conn.commit()
    finally:
        cur.close()


def get_student_profile(student_id: int) -> Optional[dict[str, object]]:
    """Return a student profile row joined with user metadata."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT sp.student_id,
                       sp.educator_id,
                       sp.grade_level,
                       sp.class_number,
                       sp.vocabulary_level,
                       sp.last_analyzed_at,
                       u.name,
                       u.email
                FROM student_profiles sp
                JOIN users u ON u.id = sp.student_id
                WHERE sp.student_id = ?;
                """,
                (student_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        cur.execute(
            """
            SELECT sp.student_id,
                   sp.educator_id,
                   sp.grade_level,
                   sp.class_number,
                   sp.vocabulary_level,
                   sp.last_analyzed_at,
                   u.name,
                   u.email
            FROM student_profiles sp
            JOIN users u ON u.id = sp.student_id
            WHERE sp.student_id = %s;
            """,
            (student_id,),
        )
        row = cur.fetchone()
        return row if row else None
    finally:
        cur.close()


def touch_student_profile_analysis(
    student_id: int, analyzed_at: Optional[datetime.datetime] = None
) -> None:
    """Update the last analyzed timestamp for a student profile."""
    conn = get_connection()
    cur = conn.cursor()
    timestamp = analyzed_at or datetime.datetime.utcnow()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                UPDATE student_profiles
                SET last_analyzed_at = ?
                WHERE student_id = ?;
                """,
                (timestamp, student_id),
            )
        else:
            cur.execute(
                """
                UPDATE student_profiles
                SET last_analyzed_at = %s
                WHERE student_id = %s;
                """,
                (timestamp, student_id),
            )
        conn.commit()
    finally:
        cur.close()


def delete_recommendations_for_upload(upload_id: int) -> None:
    """Remove recommendations associated with an upload."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                "DELETE FROM recommendations WHERE upload_id = ?;",
                (upload_id,),
            )
        else:
            cur.execute(
                "DELETE FROM recommendations WHERE upload_id = %s;",
                (upload_id,),
            )
        conn.commit()
    finally:
        cur.close()


def create_recommendations(
    *,
    student_id: int,
    upload_id: int,
    records: Sequence[dict[str, object]],
) -> None:
    """Insert a batch of recommendation rows for a student."""
    if not records:
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.executemany(
                """
                INSERT INTO recommendations (
                    word,
                    definition,
                    rationale,
                    difficulty_score,
                    example_sentence,
                    status,
                    pinned,
                    student_id,
                    upload_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    (
                        rec["word"],
                        rec["definition"],
                        rec["rationale"],
                        int(rec["difficulty_score"]),
                        rec["example_sentence"],
                        rec.get("status", "pending"),
                        1 if rec.get("pinned", False) else 0,
                        student_id,
                        upload_id,
                    )
                    for rec in records
                ],
            )
        else:
            cur.executemany(
                """
                INSERT INTO recommendations (
                    word,
                    definition,
                    rationale,
                    difficulty_score,
                    example_sentence,
                    status,
                    pinned,
                    student_id,
                    upload_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                [
                    (
                        rec["word"],
                        rec["definition"],
                        rec["rationale"],
                        int(rec["difficulty_score"]),
                        rec["example_sentence"],
                        rec.get("status", "pending"),
                        bool(rec.get("pinned", False)),
                        student_id,
                        upload_id,
                    )
                    for rec in records
                ],
            )
        conn.commit()
    finally:
        cur.close()


def list_recommendations_for_upload(upload_id: int) -> list[dict[str, object]]:
    """Return recommendations created for the given upload."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT id,
                       student_id,
                       upload_id,
                       word,
                       definition,
                       rationale,
                       difficulty_score,
                       example_sentence,
                       status,
                       pinned,
                       created_at
                FROM recommendations
                WHERE upload_id = ?
                ORDER BY created_at ASC;
                """,
                (upload_id,),
            )
            rows = cur.fetchall() or []
            return [dict(row) for row in rows]
        cur.execute(
            """
            SELECT id,
                   student_id,
                   upload_id,
                   word,
                   definition,
                   rationale,
                   difficulty_score,
                   example_sentence,
                   status,
                   pinned,
                   created_at
            FROM recommendations
            WHERE upload_id = %s
            ORDER BY created_at ASC;
            """,
            (upload_id,),
        )
        rows = cur.fetchall() or []
        return rows
    finally:
        cur.close()


def ensure_student_progress_row(student_id: int) -> None:
    """Ensure a student progress row exists for the student."""
    conn = get_connection()
    cur = conn.cursor()
    select_query = "SELECT 1 FROM student_progress WHERE student_id = %s;"
    insert_query = "INSERT INTO student_progress (student_id) VALUES (%s);"
    if _backend == "sqlite":
        select_query = select_query.replace("%s", "?")
        insert_query = insert_query.replace("%s", "?")
    try:
        cur.execute(select_query, (student_id,))
        existing = cur.fetchone()
        if existing is not None:
            return
        cur.execute(insert_query, (student_id,))
        conn.commit()
    finally:
        cur.close()


def get_student_progress(student_id: int) -> Optional[dict[str, object]]:
    """Return the student progress row if it exists."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT student_id, xp, streak_count, last_quiz_at
        FROM student_progress
        WHERE student_id = %s;
    """
    if _backend == "sqlite":
        query = query.replace("%s", "?")
    try:
        cur.execute(query, (student_id,))
        row = cur.fetchone()
        if row is None:
            return None
        if _backend == "sqlite":
            return dict(row)
        return row  # type: ignore[return-value]
    finally:
        cur.close()


def list_badges_for_student(student_id: int) -> list[dict[str, object]]:
    """Return badges earned by the student ordered by earn date."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT id, badge_type, earned_at
        FROM badges
        WHERE student_id = %s
        ORDER BY earned_at ASC, id ASC;
    """
    if _backend == "sqlite":
        query = query.replace("%s", "?")
    try:
        cur.execute(query, (student_id,))
        rows = cur.fetchall() or []
        if _backend == "sqlite":
            return [dict(row) for row in rows]
        return rows  # type: ignore[return-value]
    finally:
        cur.close()


def list_approved_words_for_student(
    student_id: int,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, object]]:
    """Return approved recommendations for the student."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT
            id,
            word,
            definition,
            rationale,
            difficulty_score,
            example_sentence,
            pinned,
            created_at
        FROM recommendations
        WHERE student_id = %s AND status = 'approved'
        ORDER BY pinned DESC, created_at DESC, id DESC
        LIMIT %s OFFSET %s;
    """
    params: tuple[object, ...] = (student_id, limit, offset)
    if _backend == "sqlite":
        query = query.replace("%s", "?")
    try:
        cur.execute(query, params)
        rows = cur.fetchall() or []
        normalized: list[dict[str, object]] = []
        for row in rows:
            if _backend == "sqlite":
                normalized.append(dict(row))
            else:
                normalized.append(dict(row))
        return normalized
    finally:
        cur.close()


def list_word_mastery_for_student(student_id: int) -> list[dict[str, object]]:
    """Return word mastery progress for the student."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT
            student_id,
            word_id,
            mastery_stage,
            correct_count,
            last_practiced_at
        FROM word_mastery
        WHERE student_id = %s
        ORDER BY word_id ASC;
    """
    if _backend == "sqlite":
        query = query.replace("%s", "?")
    try:
        cur.execute(query, (student_id,))
        rows = cur.fetchall() or []
        if _backend == "sqlite":
            return [dict(row) for row in rows]
        return rows  # type: ignore[return-value]
    finally:
        cur.close()


def list_quiz_candidates(student_id: int, limit: int = 200) -> list[dict[str, object]]:
    """Return approved words that are not yet mastered for quiz generation."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT
            r.id,
            r.word,
            r.definition,
            r.example_sentence,
            r.created_at,
            COALESCE(wm.correct_count, 0) AS correct_count,
            wm.mastery_stage,
            wm.last_practiced_at
        FROM recommendations r
        LEFT JOIN word_mastery wm
            ON wm.student_id = r.student_id
            AND wm.word_id = r.id
        WHERE r.student_id = %s
          AND r.status = 'approved'
          AND (wm.correct_count IS NULL OR wm.correct_count < 3)
        ORDER BY r.created_at DESC, r.id DESC
        LIMIT %s;
    """
    params: tuple[object, ...] = (student_id, limit)
    if _backend == "sqlite":
        query = query.replace("%s", "?")
    try:
        cur.execute(query, params)
        rows = cur.fetchall() or []
        if _backend == "sqlite":
            return [dict(row) for row in rows]
        return rows  # type: ignore[return-value]
    finally:
        cur.close()


def get_student_recommendations_by_ids(
    student_id: int,
    word_ids: Sequence[int],
) -> dict[int, dict[str, object]]:
    """Return recommendation details for the provided word identifiers."""
    if not word_ids:
        return {}

    conn = get_connection()
    cur = conn.cursor()
    placeholders = ", ".join(["%s"] * len(word_ids))
    query = f"""
        SELECT id, word, definition, example_sentence, difficulty_score
        FROM recommendations
        WHERE student_id = %s
          AND status = 'approved'
          AND id IN ({placeholders});
    """
    params: list[object] = [student_id, *word_ids]
    if _backend == "sqlite":
        query = query.replace("%s", "?")
    try:
        cur.execute(query, tuple(params))
        rows = cur.fetchall() or []
        result: dict[int, dict[str, object]] = {}
        for row in rows:
            if _backend == "sqlite":
                row = dict(row)
            result[int(row["id"])] = {
                "id": row["id"],
                "word": row["word"],
                "definition": row["definition"],
                "example_sentence": row.get("example_sentence"),
                "difficulty_score": row.get("difficulty_score"),
            }
        return result
    finally:
        cur.close()


def record_quiz_attempts(
    *,
    student_id: int,
    attempts: Sequence[dict[str, object]],
    attempted_at: Optional[datetime.datetime] = None,
) -> None:
    """Persist quiz attempt rows."""
    if not attempts:
        return

    timestamp = attempted_at or datetime.datetime.utcnow()
    conn = get_connection()
    cur = conn.cursor()
    rows: list[tuple[object, ...]] = []

    for entry in attempts:
        word_id_raw = entry.get("word_id")
        if word_id_raw is None:
            continue
        try:
            word_id = int(word_id_raw)
        except (TypeError, ValueError):
            continue
        correct = bool(entry.get("correct"))
        if _backend == "sqlite":
            rows.append((student_id, word_id, 1 if correct else 0, timestamp))
        else:
            rows.append((student_id, word_id, correct, timestamp))

    if not rows:
        cur.close()
        return

    try:
        if _backend == "sqlite":
            cur.executemany(
                """
                INSERT INTO quiz_attempts (student_id, word_id, correct, attempted_at)
                VALUES (?, ?, ?, ?);
                """,
                rows,
            )
        else:
            cur.executemany(
                """
                INSERT INTO quiz_attempts (student_id, word_id, correct, attempted_at)
                VALUES (%s, %s, %s, %s);
                """,
                rows,
            )
        conn.commit()
    finally:
        cur.close()


def update_word_mastery_from_results(
    *,
    student_id: int,
    results: Sequence[dict[str, object]],
    attempted_at: Optional[datetime.datetime] = None,
) -> dict[str, object]:
    """Apply quiz results to word mastery records."""
    if not results:
        return {"mastered_gained": 0, "updated_ids": []}

    timestamp = attempted_at or datetime.datetime.utcnow()
    conn = get_connection()
    cur = conn.cursor()
    mastered_gained = 0
    updated_ids: list[int] = []

    select_query = """
        SELECT mastery_stage, correct_count
        FROM word_mastery
        WHERE student_id = %s AND word_id = %s;
    """
    if _backend == "sqlite":
        select_query = select_query.replace("%s", "?")

    try:
        for entry in results:
            word_id_raw = entry.get("word_id")
            if word_id_raw is None:
                continue
            try:
                word_id = int(word_id_raw)
            except (TypeError, ValueError):
                continue

            increment = entry.get("increment", 0)
            try:
                increment_value = int(increment)
            except (TypeError, ValueError):
                increment_value = 0
            increment_value = max(0, increment_value)

            cur.execute(select_query, (student_id, word_id))
            row = cur.fetchone()
            if row is not None and _backend == "sqlite":
                row = dict(row)

            existing_correct = 0
            existing_stage = "practicing"
            if row:
                existing_correct = int(row.get("correct_count") or 0)
                existing_stage = str(row.get("mastery_stage") or "practicing")

            new_correct = existing_correct + increment_value
            if new_correct > 3:
                new_correct = 3

            if new_correct >= 3:
                new_stage = "mastered"
            elif new_correct >= 2:
                new_stage = "nearly_mastered"
            else:
                new_stage = "practicing"

            is_new_mastered = new_stage == "mastered" and existing_stage != "mastered"

            if row:
                if _backend == "sqlite":
                    cur.execute(
                        """
                        UPDATE word_mastery
                        SET mastery_stage = ?, correct_count = ?, last_practiced_at = ?
                        WHERE student_id = ? AND word_id = ?;
                        """,
                        (new_stage, new_correct, timestamp, student_id, word_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE word_mastery
                        SET mastery_stage = %s, correct_count = %s, last_practiced_at = %s
                        WHERE student_id = %s AND word_id = %s;
                        """,
                        (new_stage, new_correct, timestamp, student_id, word_id),
                    )
            else:
                if _backend == "sqlite":
                    cur.execute(
                        """
                        INSERT INTO word_mastery (
                            student_id,
                            word_id,
                            mastery_stage,
                            correct_count,
                            last_practiced_at
                        ) VALUES (?, ?, ?, ?, ?);
                        """,
                        (student_id, word_id, new_stage, new_correct, timestamp),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO word_mastery (
                            student_id,
                            word_id,
                            mastery_stage,
                            correct_count,
                            last_practiced_at
                        ) VALUES (%s, %s, %s, %s, %s);
                        """,
                        (student_id, word_id, new_stage, new_correct, timestamp),
                    )

            if is_new_mastered:
                mastered_gained += 1
            updated_ids.append(word_id)

        conn.commit()
    finally:
        cur.close()

    return {"mastered_gained": mastered_gained, "updated_ids": updated_ids}


def update_student_progress_for_quiz(
    *,
    student_id: int,
    correct: int,
    total: int,
    attempted_at: Optional[datetime.datetime] = None,
) -> dict[str, object]:
    """Apply XP, streak, and last quiz updates for a completed quiz."""
    ensure_student_progress_row(student_id)

    timestamp = attempted_at or datetime.datetime.utcnow()
    conn = get_connection()
    cur = conn.cursor()

    select_query = """
        SELECT xp, streak_count, last_quiz_at
        FROM student_progress
        WHERE student_id = %s;
    """
    if _backend == "sqlite":
        select_query = select_query.replace("%s", "?")

    cur.execute(select_query, (student_id,))
    row = cur.fetchone()
    if row is not None and _backend == "sqlite":
        row = dict(row)

    xp_current = 0
    streak_current = 0
    last_quiz_at: Optional[datetime.datetime] = None

    if row:
        xp_current = int(row.get("xp") or 0)
        streak_current = int(row.get("streak_count") or 0)
        raw_last_quiz = row.get("last_quiz_at")
        if isinstance(raw_last_quiz, datetime.datetime):
            last_quiz_at = raw_last_quiz
        elif isinstance(raw_last_quiz, str) and raw_last_quiz:
            try:
                last_quiz_at = datetime.datetime.fromisoformat(raw_last_quiz)
            except ValueError:
                last_quiz_at = None

    xp_gain = max(0, int(correct)) * 10
    bonus = 0
    if total > 0 and correct >= 0:
        accuracy = correct / total
        if accuracy >= 0.7:
            bonus = 50
    xp_delta = xp_gain + bonus
    xp_updated = xp_current + xp_delta

    new_streak = 1
    if last_quiz_at is not None:
        if timestamp < last_quiz_at:
            new_streak = max(1, streak_current)
        else:
            delta_days = (timestamp.date() - last_quiz_at.date()).days
            delta_seconds = (timestamp - last_quiz_at).total_seconds()
            if delta_days == 0:
                new_streak = max(1, streak_current)
            elif delta_days == 1 or delta_seconds <= 48 * 3600:
                new_streak = max(1, streak_current) + 1
            else:
                new_streak = 1
    else:
        new_streak = 1

    if _backend == "sqlite":
        cur.execute(
            """
            UPDATE student_progress
            SET xp = ?, streak_count = ?, last_quiz_at = ?
            WHERE student_id = ?;
            """,
            (xp_updated, new_streak, timestamp, student_id),
        )
    else:
        cur.execute(
            """
            UPDATE student_progress
            SET xp = %s, streak_count = %s, last_quiz_at = %s
            WHERE student_id = %s;
            """,
            (xp_updated, new_streak, timestamp, student_id),
        )
    conn.commit()
    cur.close()

    return {
        "xp": xp_updated,
        "xp_delta": xp_delta,
        "bonus": bonus,
        "streak_count": new_streak,
        "last_quiz_at": timestamp,
        "level": compute_level(xp_updated),
    }


def count_mastered_words(student_id: int) -> int:
    """Return the number of mastered words for a student."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT COUNT(*) AS total
        FROM word_mastery
        WHERE student_id = %s
          AND mastery_stage = 'mastered';
    """
    if _backend == "sqlite":
        query = query.replace("%s", "?")
    try:
        cur.execute(query, (student_id,))
        row = cur.fetchone()
        if row is None:
            return 0
        if _backend == "sqlite":
            return int(row["total"])
        return int(row["total"])
    finally:
        cur.close()


def award_badges_if_needed(student_id: int, mastered_total: int) -> list[str]:
    """Award milestone badges if thresholds have been reached."""
    thresholds = [
        (10, "10_words"),
        (50, "50_words"),
        (100, "100_words"),
    ]
    existing = {
        str(badge.get("badge_type"))
        for badge in list_badges_for_student(student_id)
    }

    earned: list[str] = []
    if mastered_total <= 0:
        return earned

    conn = get_connection()
    cur = conn.cursor()
    try:
        for threshold, badge_type in thresholds:
            if mastered_total >= threshold and badge_type not in existing:
                if _backend == "sqlite":
                    cur.execute(
                        """
                        INSERT INTO badges (student_id, badge_type)
                        VALUES (?, ?);
                        """,
                        (student_id, badge_type),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO badges (student_id, badge_type)
                        VALUES (%s, %s);
                        """,
                        (student_id, badge_type),
                    )
                earned.append(badge_type)
        if earned:
            conn.commit()
    finally:
        cur.close()

    return earned


def compute_level(xp: int) -> int:
    """Compute the student level from experience points."""
    if xp < 0:
        xp = 0
    return xp // 500


def list_recommendations_for_educator_filtered(
    *,
    educator_id: int,
    student_id: Optional[int] = None,
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    date_from: Optional[datetime.datetime] = None,
    date_to: Optional[datetime.datetime] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, object]]:
    """Return educator-scoped recommendations with optional filters."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        conditions = ["sp.educator_id = %s"]
        params: list[object] = [educator_id]

        if student_id is not None:
            conditions.append("r.student_id = %s")
            params.append(student_id)

        if difficulty_min is not None:
            conditions.append("r.difficulty_score >= %s")
            params.append(difficulty_min)

        if difficulty_max is not None:
            conditions.append("r.difficulty_score <= %s")
            params.append(difficulty_max)

        if date_from is not None:
            conditions.append("r.created_at >= %s")
            params.append(date_from)

        if date_to is not None:
            conditions.append("r.created_at <= %s")
            params.append(date_to)

        if status:
            conditions.append("r.status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                r.id,
                r.student_id,
                u.name AS student_name,
                r.word,
                r.definition,
                r.rationale,
                r.difficulty_score,
                r.example_sentence,
                r.status,
                r.pinned,
                r.created_at
            FROM recommendations r
            JOIN student_profiles sp ON sp.student_id = r.student_id
            JOIN users u ON u.id = r.student_id
            WHERE {where_clause}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT %s OFFSET %s;
        """
        params.extend([limit, offset])

        if _backend == "sqlite":
            query = query.replace("%s", "?")
        cur.execute(query, tuple(params))
        rows = cur.fetchall() or []
        if _backend == "sqlite":
            rows = [dict(row) for row in rows]
        normalized: list[dict[str, object]] = []
        for row in rows:
            pinned_value = row.get("pinned")
            normalized.append(
                {
                    "id": row["id"],
                    "student_id": row["student_id"],
                    "student_name": row.get("student_name"),
                    "word": row["word"],
                    "definition": row["definition"],
                    "rationale": row["rationale"],
                    "difficulty_score": row["difficulty_score"],
                    "example_sentence": row["example_sentence"],
                    "status": row["status"],
                    "pinned": bool(pinned_value),
                    "created_at": row["created_at"],
                }
            )
        return normalized
    finally:
        cur.close()


def count_recommendations_for_educator_filtered(
    *,
    educator_id: int,
    student_id: Optional[int] = None,
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    date_from: Optional[datetime.datetime] = None,
    date_to: Optional[datetime.datetime] = None,
    status: Optional[str] = None,
) -> int:
    """Return count of recommendations for educator given filters."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        conditions = ["sp.educator_id = %s"]
        params: list[object] = [educator_id]

        if student_id is not None:
            conditions.append("r.student_id = %s")
            params.append(student_id)

        if difficulty_min is not None:
            conditions.append("r.difficulty_score >= %s")
            params.append(difficulty_min)

        if difficulty_max is not None:
            conditions.append("r.difficulty_score <= %s")
            params.append(difficulty_max)

        if date_from is not None:
            conditions.append("r.created_at >= %s")
            params.append(date_from)

        if date_to is not None:
            conditions.append("r.created_at <= %s")
            params.append(date_to)

        if status:
            conditions.append("r.status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT COUNT(*) AS total
            FROM recommendations r
            JOIN student_profiles sp ON sp.student_id = r.student_id
            WHERE {where_clause};
        """

        if _backend == "sqlite":
            query = query.replace("%s", "?")
        cur.execute(query, tuple(params))
        row = cur.fetchone()
        if _backend == "sqlite" and row is not None:
            return int(row["total"])
        if row is None:
            return 0
        return int(row["total"])
    finally:
        cur.close()


def update_recommendations_status_scoped(
    *,
    educator_id: int,
    ids: Sequence[int],
    status: str,
) -> int:
    """Update recommendation status for educator-owned records."""
    if not ids:
        return 0

    conn = get_connection()
    cur = conn.cursor()
    try:
        placeholders = ", ".join(["%s"] * len(ids))
        query = f"""
            UPDATE recommendations
            SET status = %s
            WHERE id IN ({placeholders})
              AND student_id IN (
                  SELECT sp.student_id
                  FROM student_profiles sp
                  WHERE sp.educator_id = %s
              );
        """
        params = [status, *ids, educator_id]
        if _backend == "sqlite":
            query = query.replace("%s", "?")
        cur.execute(query, tuple(params))
        affected = cur.rowcount or 0
        conn.commit()
        return int(affected)
    finally:
        cur.close()


def update_recommendation_rationale_scoped(
    *,
    educator_id: int,
    recommendation_id: int,
    rationale: str,
) -> bool:
    """Update rationale if recommendation belongs to educator."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        query = """
            UPDATE recommendations
            SET rationale = %s
            WHERE id = %s
              AND student_id IN (
                  SELECT sp.student_id
                  FROM student_profiles sp
                  WHERE sp.educator_id = %s
              );
        """
        params = [rationale, recommendation_id, educator_id]
        if _backend == "sqlite":
            query = query.replace("%s", "?")
        cur.execute(query, tuple(params))
        affected = cur.rowcount or 0
        conn.commit()
        return affected > 0
    finally:
        cur.close()


def update_recommendation_pinned_scoped(
    *,
    educator_id: int,
    recommendation_id: int,
    pinned: bool,
) -> bool:
    """Toggle pinned flag scoped to educator."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        pinned_value = 1 if pinned else 0
        if _backend != "sqlite":
            pinned_value = bool(pinned)
        query = """
            UPDATE recommendations
            SET pinned = %s
            WHERE id = %s
              AND student_id IN (
                  SELECT sp.student_id
                  FROM student_profiles sp
                  WHERE sp.educator_id = %s
              );
        """
        params = [pinned_value, recommendation_id, educator_id]
        if _backend == "sqlite":
            query = query.replace("%s", "?")
        cur.execute(query, tuple(params))
        affected = cur.rowcount or 0
        conn.commit()
        return affected > 0
    finally:
        cur.close()


def get_baseline_words_for_grade(
    grade_level: int, limit: int = 200
) -> list[dict[str, object]]:
    """Fetch baseline words for a grade level."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _backend == "sqlite":
            cur.execute(
                """
                SELECT word, definition, difficulty
                FROM baseline_words
                WHERE grade_level = ?
                ORDER BY difficulty ASC, word ASC
                LIMIT ?;
                """,
                (grade_level, limit),
            )
            rows = cur.fetchall() or []
            return [dict(row) for row in rows]
        cur.execute(
            """
            SELECT word, definition, difficulty
            FROM baseline_words
            WHERE grade_level = %s
            ORDER BY difficulty ASC, word ASC
            LIMIT %s;
            """,
            (grade_level, limit),
        )
        rows = cur.fetchall() or []
        return rows
    finally:
        cur.close()

