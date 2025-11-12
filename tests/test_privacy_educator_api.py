from __future__ import annotations

import csv
import io

import pytest

from app.security import hash_password
from models import create_student_profile, create_user


def _login(client, identifier: str, password: str) -> None:
    response = client.post(
        "/login",
        data={"identifier": identifier, "password": password, "role": "educator"},
        follow_redirects=False,
    )
    assert response.status_code == 302


@pytest.fixture()
def educator_setup(app_context):
    educator_password = "TeachPass123!"
    educator = create_user(
        name="Teacher Example",
        email="teacher@example.com",
        username="teacher_user",
        password_hash=hash_password(educator_password),
        role="educator",
    )

    student_one = create_user(
        name="Student Alpha",
        email="student.alpha@example.com",
        username="student_alpha",
        password_hash=hash_password("Student123!"),
        role="student",
    )
    create_student_profile(
        student_id=student_one.id,
        educator_id=educator.id,
        grade_level=6,
        class_number=601,
        vocabulary_level=450,
    )

    student_two = create_user(
        name="Student Beta",
        email="student.beta@example.com",
        username="student_beta",
        password_hash=hash_password("Student456!"),
        role="student",
    )
    create_student_profile(
        student_id=student_two.id,
        educator_id=educator.id,
        grade_level=7,
        class_number=701,
        vocabulary_level=550,
    )

    student_three = create_user(
        name="Student Gamma",
        email="student.gamma@example.com",
        username="student_gamma",
        password_hash=hash_password("Student789!"),
        role="student",
    )
    create_student_profile(
        student_id=student_three.id,
        educator_id=educator.id,
        grade_level=6,
        class_number=602,
        vocabulary_level=480,
    )

    return {
        "educator": educator,
        "password": educator_password,
        "students": [student_one, student_two, student_three],
    }


def _csv_rows(response) -> list[list[str]]:
    buffer = io.StringIO(response.data.decode("utf-8"))
    reader = csv.reader(buffer)
    return list(reader)


def test_export_all_students_includes_all_names(client, educator_setup):
    educator = educator_setup["educator"]
    students = educator_setup["students"]

    _login(client, educator.username, educator_setup["password"])
    response = client.get("/api/educator/export")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"

    rows = _csv_rows(response)
    assert rows[0] == [
        "id",
        "name",
        "grade_level",
        "class_number",
        "vocabulary_level",
        "pending_words",
        "last_upload_at",
    ]
    flattened = " ".join(" ".join(row) for row in rows[1:])
    for student in students:
        assert student.name in flattened


def test_export_grade_filters_students(client, educator_setup):
    educator = educator_setup["educator"]
    students = educator_setup["students"]

    _login(client, educator.username, educator_setup["password"])
    response = client.get("/api/educator/export/grade/6")
    assert response.status_code == 200

    rows = _csv_rows(response)
    names = {row[1] for row in rows[1:]}
    sixth_grade = {s.name for s in students if s.username in {"student_alpha", "student_gamma"}}
    seventh_grade = {s.name for s in students if s.username == "student_beta"}
    assert sixth_grade.issubset(names)
    assert names.isdisjoint(seventh_grade)


def test_export_grade_invalid_returns_error(client, educator_setup):
    educator = educator_setup["educator"]
    _login(client, educator.username, educator_setup["password"])

    response = client.get("/api/educator/export/grade/9")
    assert response.status_code == 400
    payload = response.get_json()
    assert "Invalid grade level" in payload["error"]


def test_export_class_filters_students(client, educator_setup):
    educator = educator_setup["educator"]
    students = educator_setup["students"]

    _login(client, educator.username, educator_setup["password"])
    response = client.get("/api/educator/export/class/6/601")
    assert response.status_code == 200

    rows = _csv_rows(response)
    names = {row[1] for row in rows[1:]}
    assert "Student Alpha" in names
    assert "Student Gamma" not in names
    assert "Student Beta" not in names


def test_export_class_invalid_returns_error(client, educator_setup):
    educator = educator_setup["educator"]
    _login(client, educator.username, educator_setup["password"])

    response = client.get("/api/educator/export/class/6/999")
    assert response.status_code == 400
    payload = response.get_json()
    assert "Invalid class number" in payload["error"]

