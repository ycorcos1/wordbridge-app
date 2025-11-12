from __future__ import annotations

import datetime
import uuid

from app.security import hash_password
from app.services.quizzes import score_quiz_and_update
from models import (
    count_mastered_words,
    create_recommendations,
    create_student_profile,
    create_upload_record,
    create_user,
    ensure_student_progress_row,
    get_connection,
    list_approved_words_for_student,
)


def _unique(label: str) -> str:
    return f"{label}_{uuid.uuid4().hex[:8]}"


def _create_student_with_words(word_count: int = 10):
    educator = create_user(
        name="Educator Gamification",
        email=f"{_unique('educator')}@example.com",
        username=_unique("educator"),
        password_hash=hash_password("TeachPass123!"),
        role="educator",
    )

    student = create_user(
        name="Student Gamification",
        email=f"{_unique('student')}@example.com",
        username=_unique("student"),
        password_hash=hash_password("StudentQuiz123!"),
        role="student",
    )
    create_student_profile(
        student_id=student.id,
        educator_id=educator.id,
        grade_level=8,
        class_number=801,
        vocabulary_level=700,
    )
    ensure_student_progress_row(student.id)

    upload_id = create_upload_record(
        educator_id=educator.id,
        student_id=student.id,
        file_path=f"/tmp/{_unique('upload')}.txt",
        filename="gamification_sample.txt",
        status="completed",
    )

    records = [
        {
            "word": f"challenge_{idx}",
            "definition": f"Challenge definition {idx}",
            "rationale": "Supports streak testing.",
            "difficulty_score": 5,
            "example_sentence": f"Example sentence {idx}.",
            "status": "approved",
        }
        for idx in range(1, word_count + 1)
    ]
    create_recommendations(student_id=student.id, upload_id=upload_id, records=records)

    return student


def test_streak_progression_and_badge_awards(app_context):
    student = _create_student_with_words(10)
    approved_words = list_approved_words_for_student(student.id)
    answers_all_correct = [
        {"word_id": entry["id"], "answer": entry["definition"]}
        for entry in approved_words
    ]

    attempt_windows = [
        datetime.datetime(2024, 1, 1, 9, 0, 0),
        datetime.datetime(2024, 1, 2, 9, 30, 0),
        datetime.datetime(2024, 1, 4, 8, 0, 0),
    ]

    results = []
    for window in attempt_windows:
        summary = score_quiz_and_update(
            student.id,
            [dict(answer) for answer in answers_all_correct],
            attempted_at=window,
        )
        results.append(summary)

    first, second, third = results

    assert first["correct"] == 10
    assert first["xp_earned"] == 150
    assert first["progress"]["streak_count"] == 1
    assert first["progress"]["xp"] == 150

    assert second["xp_earned"] == 150
    assert second["progress"]["streak_count"] == 2
    assert second["progress"]["xp"] == 300

    assert third["xp_earned"] == 150
    assert third["progress"]["streak_count"] == 3
    assert third["progress"]["xp"] == 450
    assert "10_words" in third["badges_awarded"]
    assert third["mastered_gained"] == 10

    mastered_total = count_mastered_words(student.id)
    assert mastered_total == 10

    conn = get_connection()
    cur = conn.cursor()
    try:
        if conn.__class__.__module__.startswith("sqlite3"):
            cur.execute(
                "SELECT COUNT(*) FROM quiz_attempts WHERE student_id = ?",
                (student.id,),
            )
            attempts_count = cur.fetchone()[0]
        else:
            cur.execute(
                "SELECT COUNT(*) FROM quiz_attempts WHERE student_id = %s",
                (student.id,),
            )
            attempts_count = cur.fetchone()[0]
    finally:
        cur.close()

    assert attempts_count == len(answers_all_correct) * len(attempt_windows)
