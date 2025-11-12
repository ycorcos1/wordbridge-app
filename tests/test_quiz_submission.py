from __future__ import annotations
import uuid

from app.security import hash_password
from models import (
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


def _create_student_with_words(word_count: int = 6):
    educator = create_user(
        name="Educator Submit",
        email=f"{_unique('educator')}@example.com",
        username=_unique("educator"),
        password_hash=hash_password("TeachPass123!"),
        role="educator",
    )

    student_password = "StudentSubmit123!"
    student = create_user(
        name="Student Submit",
        email=f"{_unique('student')}@example.com",
        username=_unique("student"),
        password_hash=hash_password(student_password),
        role="student",
    )
    create_student_profile(
        student_id=student.id,
        educator_id=educator.id,
        grade_level=6,
        class_number=601,
        vocabulary_level=580,
    )
    ensure_student_progress_row(student.id)

    upload_id = create_upload_record(
        educator_id=educator.id,
        student_id=student.id,
        file_path=f"/tmp/{_unique('upload')}.txt",
        filename="submit_sample.txt",
        status="completed",
    )

    records = [
        {
            "word": f"vocab_{idx}",
            "definition": f"Definition #{idx}",
            "rationale": "Supports mastery progression.",
            "difficulty_score": (idx % 10) + 1,
            "example_sentence": f"Usage example #{idx}.",
            "status": "approved",
        }
        for idx in range(1, word_count + 1)
    ]
    create_recommendations(student_id=student.id, upload_id=upload_id, records=records)

    return {
        "student": student,
        "student_password": student_password,
    }


def _login_student(client, identifier: str, password: str) -> None:
    response = client.post(
        "/login",
        data={
            "identifier": identifier,
            "password": password,
            "role": "student",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_quiz_submission_updates_progress_and_records(client, app_context):
    setup = _create_student_with_words()
    student = setup["student"]
    password = setup["student_password"]

    approved_words = list_approved_words_for_student(student.id)
    answers = []
    for index, entry in enumerate(approved_words):
        if index < 4:
            answers.append({"word_id": entry["id"], "answer": entry["definition"]})
        else:
            answers.append({"word_id": entry["id"], "answer": "Incorrect choice"})

    _login_student(client, student.username, password)
    response = client.post("/api/quiz/submit", json={"answers": answers})
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["correct"] == 4
    assert payload["total"] == len(answers)
    assert payload["xp_earned"] == 40
    assert payload["bonus_awarded"] == 0

    progress = payload["progress"]
    assert progress["xp"] == 40
    assert progress["streak_count"] == 1
    assert progress["last_quiz_at"]

    assert payload["mastered_gained"] == 0
    assert payload["badges_awarded"] == []

    conn = get_connection()
    cur = conn.cursor()
    try:
        if conn.__class__.__module__.startswith("sqlite3"):
            cur.execute(
                "SELECT COUNT(*) FROM quiz_attempts WHERE student_id = ?",
                (student.id,),
            )
            attempts_count = cur.fetchone()[0]

            cur.execute(
                "SELECT correct_count FROM word_mastery WHERE student_id = ? AND word_id = ?",
                (student.id, approved_words[0]["id"]),
            )
            correct_count_first = cur.fetchone()[0]

            cur.execute(
                "SELECT correct_count FROM word_mastery WHERE student_id = ? AND word_id = ?",
                (student.id, approved_words[-1]["id"]),
            )
            correct_count_last = cur.fetchone()[0]
        else:
            cur.execute(
                "SELECT COUNT(*) FROM quiz_attempts WHERE student_id = %s",
                (student.id,),
            )
            attempts_count = cur.fetchone()[0]

            cur.execute(
                "SELECT correct_count FROM word_mastery WHERE student_id = %s AND word_id = %s",
                (student.id, approved_words[0]["id"]),
            )
            correct_count_first = cur.fetchone()[0]

            cur.execute(
                "SELECT correct_count FROM word_mastery WHERE student_id = %s AND word_id = %s",
                (student.id, approved_words[-1]["id"]),
            )
            correct_count_last = cur.fetchone()[0]
    finally:
        cur.close()

    assert attempts_count == len(answers)
    assert correct_count_first == 1
    assert correct_count_last == 0
