from app.security import hash_password
from models import create_user


def login(client, identifier: str, password: str, role: str):
    return client.post(
        "/login",
        data={
            "identifier": identifier,
            "password": password,
            "role": role,
        },
        follow_redirects=True,
    )


def test_student_cannot_access_educator_dashboard(client, app_context):
    password = "StrongPass123"
    create_user(
        name="Student One",
        email="student1@example.com",
        username="student1",
        password_hash=hash_password(password),
        role="student",
    )

    login(client, "student1", password, "student")

    response = client.get("/educator/dashboard")
    assert response.status_code == 403


def test_educator_cannot_access_student_dashboard(client, app_context):
    password = "StrongPass123"
    create_user(
        name="Teacher One",
        email="teacher1@example.com",
        username="teacher1",
        password_hash=hash_password(password),
        role="educator",
    )

    login(client, "teacher1", password, "educator")

    response = client.get("/student/dashboard")
    assert response.status_code == 403

