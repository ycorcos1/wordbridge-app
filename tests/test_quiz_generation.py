from __future__ import annotations

import uuid

from app.security import hash_password
from models import (
    create_recommendations,
    create_student_profile,
    create_upload_record,
    create_user,
    ensure_student_progress_row,
    list_approved_words_for_student,
    update_word_mastery_from_results,
)


def _unique(label: str) -> str:
    return f"{label}_{uuid.uuid4().hex[:8]}"


def _create_student_with_words(word_count: int):
    educator = create_user(
        name="Educator Quiz",
        email=f"{_unique('educator')}@example.com",
        username=_unique("educator"),
        password_hash=hash_password("TeachPass123!"),
        role="educator",
    )

    student_password = "StudentQuiz123!"
    student = create_user(
        name="Student Quiz",
        email=f"{_unique('student')}@example.com",
        username=_unique("student"),
        password_hash=hash_password(student_password),
        role="student",
    )
    create_student_profile(
        student_id=student.id,
        educator_id=educator.id,
        grade_level=7,
        class_number=701,
        vocabulary_level=620,
    )
    ensure_student_progress_row(student.id)

    upload_id = create_upload_record(
        educator_id=educator.id,
        student_id=student.id,
        file_path=f"/tmp/{_unique('upload')}.txt",
        filename="quiz_sample.txt",
        status="completed",
    )

    records = [
        {
            "word": f"word_{idx}",
            "definition": f"Definition for word {idx}",
            "rationale": "Supports targeted vocabulary growth.",
            "difficulty_score": (idx % 10) + 1,
            "example_sentence": f"Example usage for word {idx}.",
            "status": "approved",
        }
        for idx in range(1, word_count + 1)
    ]
    create_recommendations(student_id=student.id, upload_id=upload_id, records=records)

    return {
        "educator": educator,
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


def test_quiz_generation_requires_minimum_words(client, app_context):
    setup = _create_student_with_words(3)
    student = setup["student"]
    password = setup["student_password"]

    _login_student(client, student.username, password)

    response = client.get("/api/quiz/generate")
    assert response.status_code == 400
    payload = response.get_json()
    assert "Not enough approved words" in payload["error"]


def test_quiz_generation_omits_mastered_words(client, app_context):
    setup = _create_student_with_words(8)
    student = setup["student"]
    password = setup["student_password"]

    approved = list_approved_words_for_student(student.id)
    mastered_target = approved[0]["id"]
    update_word_mastery_from_results(
        student_id=student.id,
        results=[{"word_id": mastered_target, "increment": 3}],
    )

    _login_student(client, student.username, password)
    response = client.get("/api/quiz/generate")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["total"] == len(payload["questions"])
    assert payload["total"] == len(approved) - 1

    word_ids = {question["word_id"] for question in payload["questions"]}
    assert mastered_target not in word_ids

    for question in payload["questions"]:
        assert "definition_choices" in question
        assert len(question["definition_choices"]) >= 1
        assert question.get("correct_definition")
