from urllib.parse import urlparse

from app.security import hash_password
from models import create_user


def test_educator_signup_and_login_flow(client):
    signup_response = client.post(
        "/signup",
        data={
            "name": "Ms. Rivera",
            "username": "mrivera",
            "email": "mrivera@example.com",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!",
        },
        follow_redirects=True,
    )

    body = signup_response.get_data(as_text=True)
    assert "Educator account created successfully" in body

    login_response = client.post(
        "/login",
        data={
            "identifier": "mrivera",
            "password": "StrongPass123!",
            "role": "educator",
        },
    )

    assert login_response.status_code == 302
    assert urlparse(login_response.headers["Location"]).path == "/educator/dashboard"

    dashboard_response = client.get("/educator/dashboard")
    assert dashboard_response.status_code == 200
    body = dashboard_response.get_data(as_text=True)
    assert "Class Overview" in body or "Total Students" in body

    logout_response = client.get("/logout", follow_redirects=True)
    assert "You have been logged out." in logout_response.get_data(as_text=True)


def test_login_role_mismatch_displays_error(client, app_context):
    create_user(
        name="Teacher Two",
        email="teachertwo@example.com",
        username="teachertwo",
        password_hash=hash_password("Password123!"),
        role="educator",
    )

    response = client.post(
        "/login",
        data={
            "identifier": "teachertwo",
            "password": "Password123!",
            "role": "student",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Role mismatch" in response.get_data(as_text=True)


def test_student_login_redirects_to_student_dashboard(client, app_context):
    create_user(
        name="Student Example",
        email="student@example.com",
        username="student_example",
        password_hash=hash_password("StudentPass1!"),
        role="student",
    )

    login_response = client.post(
        "/login",
        data={
            "identifier": "student@example.com",
            "password": "StudentPass1!",
            "role": "student",
        },
    )

    assert login_response.status_code == 302
    assert urlparse(login_response.headers["Location"]).path == "/student/dashboard"

    dashboard_response = client.get("/student/dashboard")
    assert dashboard_response.status_code == 200
    body = dashboard_response.get_data(as_text=True)
    assert "WordBridge" in body or "Your Vocabulary Words" in body or "XP" in body


