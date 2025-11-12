"""Smoke tests for critical routes and health checks."""
import pytest
from urllib.parse import urlparse

from app.security import hash_password
from models import create_user


@pytest.mark.smoke
def test_health_endpoint_returns_ok(client):
    """Verify the health endpoint returns 200 with expected JSON."""
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload.get("status") == "ok"
    assert payload.get("service") == "wordbridge"


@pytest.mark.smoke
def test_index_route_unauthenticated(client):
    """Verify index route is accessible without authentication."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "WordBridge" in body or "Login" in body


@pytest.mark.smoke
def test_login_page_accessible(client):
    """Verify login page loads successfully."""
    response = client.get("/login")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "login" in body.lower() or "sign in" in body.lower()


@pytest.mark.smoke
def test_signup_page_accessible(client):
    """Verify signup page loads successfully."""
    response = client.get("/signup")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "signup" in body.lower() or "sign up" in body.lower() or "register" in body.lower()


@pytest.mark.smoke
def test_educator_dashboard_requires_authentication(client):
    """Verify educator dashboard redirects when unauthenticated."""
    response = client.get("/educator/dashboard", follow_redirects=False)
    assert response.status_code in (302, 401, 403)
    if response.status_code == 302:
        location = urlparse(response.headers.get("Location", "")).path
        assert location in ("/login", "/")


@pytest.mark.smoke
def test_student_dashboard_requires_authentication(client):
    """Verify student dashboard redirects when unauthenticated."""
    response = client.get("/student/dashboard", follow_redirects=False)
    assert response.status_code in (302, 401, 403)
    if response.status_code == 302:
        location = urlparse(response.headers.get("Location", "")).path
        assert location in ("/login", "/")


@pytest.mark.smoke
def test_educator_routes_block_student_access(client, app_context):
    """Verify students cannot access educator routes."""
    student = create_user(
        name="Test Student",
        email="student@test.com",
        username="teststudent",
        password_hash=hash_password("StudentPass123!"),
        role="student",
    )

    # Login as student
    login_response = client.post(
        "/login",
        data={
            "identifier": "teststudent",
            "password": "StudentPass123!",
            "role": "student",
        },
    )
    assert login_response.status_code == 302

    # Attempt to access educator route
    educator_route_response = client.get("/educator/dashboard", follow_redirects=False)
    assert educator_route_response.status_code == 403


@pytest.mark.smoke
def test_student_routes_block_educator_access(client, app_context):
    """Verify educators cannot access student routes."""
    educator = create_user(
        name="Test Educator",
        email="educator@test.com",
        username="testeducator",
        password_hash=hash_password("EducatorPass123!"),
        role="educator",
    )

    # Login as educator
    login_response = client.post(
        "/login",
        data={
            "identifier": "testeducator",
            "password": "EducatorPass123!",
            "role": "educator",
        },
    )
    assert login_response.status_code == 302

    # Attempt to access student route
    student_route_response = client.get("/student/dashboard", follow_redirects=False)
    assert student_route_response.status_code == 403

