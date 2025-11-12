from __future__ import annotations

import datetime

import pytest

from app.security import hash_password
from models import (
    create_recommendations,
    create_student_profile,
    create_upload_record,
    create_user,
    get_connection,
)


def _create_educator(username: str, email: str, password: str):
    return create_user(
        name="Educator Example",
        email=email,
        username=username,
        password_hash=hash_password(password),
        role="educator",
    )


def _create_student(
    *,
    name: str,
    username: str,
    email: str,
    password: str,
    educator_id: int,
    grade_level: int,
    vocabulary_level: int,
    class_number: int | None = None,
):
    student = create_user(
        name=name,
        email=email,
        username=username,
        password_hash=hash_password(password),
        role="student",
    )
    if class_number is None:
        class_number = grade_level * 100 + 1  # Default: 601, 701, 801
    create_student_profile(
        student_id=student.id,
        educator_id=educator_id,
        grade_level=grade_level,
        class_number=class_number,
        vocabulary_level=vocabulary_level,
    )
    return student


def _login(client, identifier: str, password: str):
    response = client.post(
        "/login",
        data={"identifier": identifier, "password": password, "role": "educator"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return response


def _set_upload_created_at(upload_id: int, timestamp: datetime.datetime):
    conn = get_connection()
    cur = conn.cursor()
    try:
        if conn.__class__.__module__.startswith("sqlite3"):
            cur.execute(
                "UPDATE uploads SET created_at = ?, processed_at = ? WHERE id = ?",
                (timestamp, timestamp, upload_id),
            )
        else:
            cur.execute(
                "UPDATE uploads SET created_at = %s, processed_at = %s WHERE id = %s",
                (timestamp, timestamp, upload_id),
            )
        conn.commit()
    finally:
        cur.close()


@pytest.fixture()
def educator_with_students(app_context):
    educator = _create_educator(
        username="dashboard_teacher",
        email="dashboard_teacher@example.com",
        password="TeachPass123!",
    )

    student_one = _create_student(
        name="Student One",
        username="student_one",
        email="student_one@example.com",
        password="StudentPass123!",
        educator_id=educator.id,
        grade_level=6,
        vocabulary_level=450,
    )

    student_two = _create_student(
        name="Student Two",
        username="student_two",
        email="student_two@example.com",
        password="StudentPass456!",
        educator_id=educator.id,
        grade_level=7,
        vocabulary_level=700,
    )

    upload_one = create_upload_record(
        educator_id=educator.id,
        student_id=student_one.id,
        file_path="/tmp/sample1.txt",
        filename="sample1.txt",
        status="completed",
    )
    upload_two = create_upload_record(
        educator_id=educator.id,
        student_id=student_two.id,
        file_path="/tmp/sample2.txt",
        filename="sample2.txt",
        status="completed",
    )

    timestamp_one = datetime.datetime(2024, 1, 2, 9, 0, 0)
    timestamp_two = datetime.datetime(2024, 1, 3, 10, 30, 0)
    _set_upload_created_at(upload_one, timestamp_one)
    _set_upload_created_at(upload_two, timestamp_two)

    create_recommendations(
        student_id=student_one.id,
        upload_id=upload_one,
        records=[
            {
                "word": "alpha",
                "definition": "Definition alpha",
                "rationale": "Rationale alpha",
                "difficulty_score": 3,
                "example_sentence": "Example alpha.",
                "status": "pending",
            },
            {
                "word": "beta",
                "definition": "Definition beta",
                "rationale": "Rationale beta",
                "difficulty_score": 4,
                "example_sentence": "Example beta.",
                "status": "approved",
            },
        ],
    )

    create_recommendations(
        student_id=student_two.id,
        upload_id=upload_two,
        records=[
            {
                "word": "gamma",
                "definition": "Definition gamma",
                "rationale": "Rationale gamma",
                "difficulty_score": 5,
                "example_sentence": "Example gamma.",
                "status": "pending",
            },
            {
                "word": "delta",
                "definition": "Definition delta",
                "rationale": "Rationale delta",
                "difficulty_score": 6,
                "example_sentence": "Example delta.",
                "status": "pending",
            },
            {
                "word": "epsilon",
                "definition": "Definition epsilon",
                "rationale": "Rationale epsilon",
                "difficulty_score": 7,
                "example_sentence": "Example epsilon.",
                "status": "rejected",
            },
        ],
    )

    return educator, student_one, student_two


def test_dashboard_api_returns_summary(client, educator_with_students):
    educator, student_one, student_two = educator_with_students
    _login(client, educator.username, "TeachPass123!")

    response = client.get("/api/educator/dashboard")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["total_students"] == 2
    assert payload["pending_recommendations"] == 3
    assert "active_streaks" not in payload
    assert "average_proficiency" not in payload

    students = {entry["id"]: entry for entry in payload["students"]}
    assert student_one.id in students
    assert student_two.id in students
    assert students[student_one.id]["pending_words"] == 1
    assert students[student_two.id]["pending_words"] == 2
    assert students[student_one.id]["last_upload_at"].startswith("2024-01-02")
    assert students[student_two.id]["last_upload_at"].startswith("2024-01-03")


def test_dashboard_page_renders_students(client, educator_with_students):
    educator, _, _ = educator_with_students
    _login(client, educator.username, "TeachPass123!")

    response = client.get("/educator/dashboard")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Student One" in body
    assert "Student Two" in body
    assert "Filter by grade" in body
    assert "Export all students CSV" in body
    assert "Export 6th grade CSV" in body
    assert "Class 601" in body
    assert "Avg proficiency: 450.0" in body


def test_student_detail_requires_ownership(client, educator_with_students):
    educator, student_one, _ = educator_with_students
    _login(client, educator.username, "TeachPass123!")

    detail_response = client.get(f"/educator/students/{student_one.id}")
    assert detail_response.status_code == 200
    detail_body = detail_response.get_data(as_text=True)
    assert "Student profile overview" in detail_body
    assert "Pending" in detail_body

    other_educator = _create_educator(
        username="other_teacher",
        email="other_teacher@example.com",
        password="OtherTeach123!",
    )
    other_student = _create_student(
        name="Other Student",
        username="other_student",
        email="other_student@example.com",
        password="OtherStudent123!",
        educator_id=other_educator.id,
        grade_level=6,
        vocabulary_level=400,
    )

    forbidden_response = client.get(f"/educator/students/{other_student.id}")
    assert forbidden_response.status_code == 404

