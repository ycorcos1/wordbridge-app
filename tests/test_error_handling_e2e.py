"""End-to-end error handling tests."""
from __future__ import annotations

import io
import uuid

import pytest

from app.jobs.worker import process_upload_job, PermanentJobError
from app.services.openai_client import OpenAIResponseError, OpenAIConfigurationError
from app.security import hash_password
from models import create_student_profile, create_upload_record, create_user
from app.repositories import uploads_repo


def _unique(label: str) -> str:
    return f"{label}_{uuid.uuid4().hex[:8]}"


class _FakeS3Client:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def upload_fileobj(self, fileobj, bucket: str, key: str) -> None:
        fileobj.seek(0)
        self.files[f"{bucket}/{key}"] = fileobj.read()
        fileobj.seek(0)

    def download_fileobj(self, bucket: str, key: str, fileobj) -> None:
        content = self.files.get(f"{bucket}/{key}", b"")
        fileobj.write(content)
        fileobj.seek(0)


@pytest.fixture()
def fake_s3_client(monkeypatch):
    fake = _FakeS3Client()

    def fake_boto_client(service_name: str, **kwargs):
        if service_name == "s3":
            return fake
        raise AssertionError(f"Unsupported service: {service_name}")

    monkeypatch.setattr("boto3.client", fake_boto_client)
    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "test-bucket")
    return fake


@pytest.fixture()
def educator_and_student(app_context):
    educator = create_user(
        name="Error Test Educator",
        email=f"{_unique('error_educator')}@example.com",
        username=_unique("error_educator"),
        password_hash=hash_password("TeacherPass123!"),
        role="educator",
    )
    student = create_user(
        name="Error Test Student",
        email=f"{_unique('error_student')}@example.com",
        username=_unique("error_student"),
        password_hash=hash_password("StudentPass123!"),
        role="student",
    )
    create_student_profile(
        student_id=student.id,
        educator_id=educator.id,
        grade_level=7,
        class_number=701,
        vocabulary_level=550,
    )
    return educator, student


def _login_as_educator(client, username: str, password: str) -> None:
    login_response = client.post(
        "/login",
        data={"identifier": username, "password": password, "role": "educator"},
    )
    assert login_response.status_code == 302


@pytest.mark.error
def test_upload_rejects_no_files(client, monkeypatch, educator_and_student):
    """Verify upload API rejects requests with no files."""
    educator, student = educator_and_student
    _login_as_educator(client, educator.username, "TeacherPass123!")

    fake_s3 = _FakeS3Client()

    def fake_boto_client(service_name: str, **kwargs):
        if service_name == "s3":
            return fake_s3
        raise AssertionError(f"Unsupported service: {service_name}")

    monkeypatch.setattr("boto3.client", fake_boto_client)
    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "test-bucket")

    response = client.post("/api/upload", data={"student_id": str(student.id)})
    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload
    assert "No files provided" in payload["error"] or "files" in payload["error"].lower()


@pytest.mark.error
def test_upload_rejects_unsupported_file_type(client, monkeypatch, educator_and_student):
    """Verify upload API rejects unsupported file types."""
    educator, student = educator_and_student
    _login_as_educator(client, educator.username, "TeacherPass123!")

    fake_s3 = _FakeS3Client()

    def fake_boto_client(service_name: str, **kwargs):
        if service_name == "s3":
            return fake_s3
        raise AssertionError(f"Unsupported service: {service_name}")

    monkeypatch.setattr("boto3.client", fake_boto_client)
    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "test-bucket")

    data = {
        "student_id": str(student.id),
        "files": (io.BytesIO(b"malicious content"), "malware.exe"),
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    payload = response.get_json()
    assert "results" in payload
    result = payload["results"][0]
    assert "error" in result
    assert "Unsupported file type" in result["error"] or "unsupported" in result["error"].lower()


@pytest.mark.error
def test_upload_rejects_oversized_file(client, monkeypatch, educator_and_student):
    """Verify upload API rejects files exceeding size limit."""
    educator, student = educator_and_student
    _login_as_educator(client, educator.username, "TeacherPass123!")

    fake_s3 = _FakeS3Client()

    def fake_boto_client(service_name: str, **kwargs):
        if service_name == "s3":
            return fake_s3
        raise AssertionError(f"Unsupported service: {service_name}")

    monkeypatch.setattr("boto3.client", fake_boto_client)
    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "test-bucket")

    # Create a file that exceeds 10MB
    oversized_content = b"x" * (11 * 1024 * 1024)  # 11MB
    data = {
        "student_id": str(student.id),
        "files": (io.BytesIO(oversized_content), "huge_file.txt"),
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    payload = response.get_json()
    assert "results" in payload
    result = payload["results"][0]
    assert "error" in result
    assert "exceeds" in result["error"].lower() or "10MB" in result["error"]


@pytest.mark.error
def test_upload_fails_when_s3_not_configured(client, monkeypatch, educator_and_student):
    """Verify upload returns error when S3 bucket is not configured."""
    educator, student = educator_and_student
    _login_as_educator(client, educator.username, "TeacherPass123!")

    monkeypatch.delenv("AWS_S3_BUCKET_NAME", raising=False)

    data = {
        "student_id": str(student.id),
        "files": (io.BytesIO(b"test content"), "sample.txt"),
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert response.status_code == 500
    payload = response.get_json()
    assert "error" in payload
    assert "AWS_S3_BUCKET_NAME" in payload["error"] or "not configured" in payload["error"].lower()


@pytest.mark.error
def test_ai_processing_handles_openai_failure(monkeypatch, app_context, fake_s3_client):
    """Verify worker handles OpenAI API failures gracefully."""
    educator = create_user(
        name="AI Error Educator",
        email=f"{_unique('ai_error')}@example.com",
        username=_unique("ai_error_educator"),
        password_hash=hash_password("TeacherPass123!"),
        role="educator",
    )
    student = create_user(
        name="AI Error Student",
        email=f"{_unique('ai_error_student')}@example.com",
        username=_unique("ai_error_student"),
        password_hash=hash_password("StudentPass123!"),
        role="student",
    )
    create_student_profile(
        student_id=student.id,
        educator_id=educator.id,
        grade_level=7,
        class_number=701,
        vocabulary_level=550,
    )

    # Store file in fake S3
    sample_text = " ".join(["Sample text for AI processing."] * 50)
    file_content = sample_text.encode("utf-8")
    s3_key = f"test-bucket/uploads/{educator.id}/{student.id}/123_sample.txt"
    fake_s3_client.files[s3_key] = file_content

    upload_id = create_upload_record(
        educator_id=educator.id,
        student_id=student.id,
        file_path=f"s3://{s3_key}",
        filename="sample.txt",
        status="pending",
    )

    # Mock OpenAI to raise an error
    def mock_openai_error(*args, **kwargs):
        raise OpenAIResponseError("OpenAI API temporarily unavailable")

    monkeypatch.setattr(
        "app.services.openai_client.generate_json_response",
        mock_openai_error,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MAX_RETRIES", "2")  # Reduce retries for faster test

    # Process job - should fail after retries
    result = process_upload_job(upload_id, s3_client=fake_s3_client)
    assert result.success is False
    assert result.error is not None

    # Verify upload status is marked as failed
    status = uploads_repo.fetch_upload(upload_id)
    assert status is not None
    assert status.get("status") == "failed"


@pytest.mark.error
def test_ai_processing_rejects_insufficient_words(monkeypatch, app_context, fake_s3_client):
    """Verify worker rejects uploads with insufficient word count."""
    educator = create_user(
        name="Word Count Educator",
        email=f"{_unique('wordcount')}@example.com",
        username=_unique("wordcount_educator"),
        password_hash=hash_password("TeacherPass123!"),
        role="educator",
    )
    student = create_user(
        name="Word Count Student",
        email=f"{_unique('wordcount_student')}@example.com",
        username=_unique("wordcount_student"),
        password_hash=hash_password("StudentPass123!"),
        role="student",
    )
    create_student_profile(
        student_id=student.id,
        educator_id=educator.id,
        grade_level=7,
        class_number=701,
        vocabulary_level=550,
    )

    # Create file with too few words (< 200 for initial analysis)
    short_text = "This is a very short text with only a few words."
    file_content = short_text.encode("utf-8")
    s3_key = f"test-bucket/uploads/{educator.id}/{student.id}/123_short.txt"
    fake_s3_client.files[s3_key] = file_content

    upload_id = create_upload_record(
        educator_id=educator.id,
        student_id=student.id,
        file_path=f"s3://{s3_key}",
        filename="short.txt",
        status="pending",
    )

    # Mock OpenAI to return valid response (won't be called due to word count check)
    def mock_openai_success(*args, **kwargs):
        return '{"recommendations": []}'

    monkeypatch.setattr(
        "app.services.openai_client.generate_json_response",
        mock_openai_success,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    # Process job - should fail due to insufficient words
    result = process_upload_job(upload_id, s3_client=fake_s3_client)
    assert result.success is False
    assert "words" in result.error.lower() or "200" in result.error

    # Verify upload status is marked as failed
    status = uploads_repo.fetch_upload(upload_id)
    assert status is not None
    assert status.get("status") == "failed"


@pytest.mark.error
def test_bad_login_attempts_show_error(client, app_context):
    """Verify bad login attempts show user-friendly error messages."""
    # Test with wrong password
    response = client.post(
        "/login",
        data={
            "identifier": "nonexistent",
            "password": "wrongpassword",
            "role": "educator",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "invalid" in body.lower() or "credentials" in body.lower() or "error" in body.lower()

    # Test with role mismatch
    educator = create_user(
        name="Role Test Educator",
        email=f"{_unique('role_test')}@example.com",
        username=_unique("role_test_educator"),
        password_hash=hash_password("Password123!"),
        role="educator",
    )

    response = client.post(
        "/login",
        data={
            "identifier": educator.username,
            "password": "Password123!",
            "role": "student",  # Wrong role
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "role" in body.lower() or "mismatch" in body.lower()


@pytest.mark.error
def test_database_error_handling(client, monkeypatch, app_context):
    """Verify routes handle database errors gracefully without exposing stack traces."""
    # This test verifies that database errors don't expose internal details
    # We'll test by attempting an operation that might fail

    # Create a user with duplicate email to trigger database error
    create_user(
        name="Duplicate Test",
        email="duplicate@example.com",
        username=_unique("duplicate1"),
        password_hash=hash_password("Password123!"),
        role="educator",
    )

    # Attempt to create another user with same email
    response = client.post(
        "/signup",
        data={
            "name": "Duplicate Test 2",
            "username": _unique("duplicate2"),
            "email": "duplicate@example.com",  # Duplicate email
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
        follow_redirects=True,
    )

    # Should show user-friendly error, not stack trace
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    # Should not contain Python traceback indicators
    assert "Traceback" not in body
    assert "File" not in body or "line" not in body.lower() or "traceback" not in body.lower()
    # Should contain user-friendly message
    assert "error" in body.lower() or "already" in body.lower() or "taken" in body.lower()

