from __future__ import annotations

from urllib.parse import urlparse

from app.security import hash_password
from models import (
    count_baseline_words_for_grade,
    create_user,
    ensure_baseline_words_loaded,
    get_connection,
    get_user_by_identifier,
)


def _create_and_login_educator(client, *, username: str, email: str, password: str) -> None:
    create_user(
        name="Educator Example",
        email=email,
        username=username,
        password_hash=hash_password(password),
        role="educator",
    )
    response = client.post(
        "/login",
        data={
            "identifier": username,
            "password": password,
            "role": "educator",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert urlparse(response.headers["Location"]).path == "/educator/dashboard"


def _fetch_student_profile(student_id: int) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT student_id, educator_id, grade_level, class_number FROM student_profiles WHERE student_id = ?",
            (student_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        cur.close()


def test_educator_add_student_form_success(client, app_context):
    ensure_baseline_words_loaded()
    _create_and_login_educator(
        client,
        username="teach_form",
        email="teach_form@example.com",
        password="TeachPass123!",
    )

    response = client.post(
        "/educator/add-student",
        data={
            "name": "Jordan Rivers",
            "grade": "6",
            "class_number": "601",
            "username": "jordan_rivers",
            "email": "jordan_rivers@example.com",
            "password": "StudentPass123!",
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Student account created successfully!" in body

    student = get_user_by_identifier("jordan_rivers")
    assert student is not None
    assert student.role == "student"

    profile = _fetch_student_profile(student.id)
    assert profile is not None
    assert profile["grade_level"] == 6

    assert count_baseline_words_for_grade(6) > 0


def test_duplicate_username_via_form_shows_error(client, app_context):
    ensure_baseline_words_loaded()
    _create_and_login_educator(
        client,
        username="teach_duplicate",
        email="teach_duplicate@example.com",
        password="TeachPass456!",
    )

    first_response = client.post(
        "/educator/add-student",
        data={
            "name": "Student One",
            "grade": "7",
            "class_number": "701",
            "username": "dup_student",
            "email": "dup_student@example.com",
            "password": "StudentPass123!",
        },
        follow_redirects=True,
    )
    assert first_response.status_code == 200

    retry_response = client.post(
        "/educator/add-student",
        data={
            "name": "Student Two",
            "grade": "7",
            "class_number": "701",
            "username": "dup_student",
            "email": "dup_student_second@example.com",
            "password": "StudentPass456!",
        },
        follow_redirects=True,
    )

    body = retry_response.get_data(as_text=True)
    assert retry_response.status_code == 200
    assert "already in use" in body


def test_api_create_student_success(client, app_context):
    ensure_baseline_words_loaded()
    _create_and_login_educator(
        client,
        username="teach_api",
        email="teach_api@example.com",
        password="TeachPass789!",
    )

    response = client.post(
        "/api/students/create",
        json={
            "name": "Taylor Brooks",
            "grade": 8,
            "class_number": 801,
            "username": "taylor_brooks",
            "email": "taylor_brooks@example.com",
            "password": "StudentPass789!",
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["username"] == "taylor_brooks"
    assert payload["grade_level"] == 8

    student = get_user_by_identifier("taylor_brooks")
    assert student is not None
    profile = _fetch_student_profile(student.id)
    assert profile is not None
    assert profile["grade_level"] == 8


def test_api_validation_error_returns_400(client, app_context):
    ensure_baseline_words_loaded()
    _create_and_login_educator(
        client,
        username="teach_api_invalid",
        email="teach_api_invalid@example.com",
        password="TeachPass321!",
    )

    response = client.post(
        "/api/students/create",
        json={
            "name": "Missing Password",
            "grade": 6,
            "username": "no_password_student",
            "email": "no_password_student@example.com",
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert "errors" in payload
    assert "password" in payload["errors"]


def test_api_duplicate_returns_conflict(client, app_context):
    ensure_baseline_words_loaded()
    _create_and_login_educator(
        client,
        username="teach_api_dup",
        email="teach_api_dup@example.com",
        password="TeachDupPass123!",
    )

    first_response = client.post(
        "/api/students/create",
        json={
            "name": "Student First",
            "grade": 7,
            "class_number": 701,
            "username": "api_dup_student",
            "email": "api_dup_student@example.com",
            "password": "ApiStudentPass123!",
        },
    )
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/students/create",
        json={
            "name": "Student Second",
            "grade": 7,
            "class_number": 701,
            "username": "api_dup_student",
            "email": "api_dup_student_second@example.com",
            "password": "ApiStudentPass456!",
        },
    )

    assert duplicate_response.status_code == 409
    payload = duplicate_response.get_json()
    assert "already in use" in payload["error"]

