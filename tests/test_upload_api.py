from __future__ import annotations

import io
from typing import Any

import pytest

from app.security import hash_password
from models import create_student_profile, create_user, get_upload_status


class _FakeS3Client:
    def __init__(self) -> None:
        self.uploads: list[tuple[Any, ...]] = []

    def upload_fileobj(self, fileobj, bucket: str, key: str) -> None:
        # simulate read for side effects and reset stream
        fileobj.read()
        fileobj.seek(0)
        self.uploads.append((bucket, key))


def _login_as_educator(client, username: str, password: str) -> None:
    login_response = client.post(
        "/login",
        data={"identifier": username, "password": password, "role": "educator"},
    )
    assert login_response.status_code == 302


@pytest.fixture()
def educator_and_student(app_context):
    educator = create_user(
        name="Upload Teacher",
        email="upload.teacher@example.com",
        username="uploadteacher",
        password_hash=hash_password("TeacherPass123!"),
        role="educator",
    )
    student = create_user(
        name="Upload Student",
        email="upload.student@example.com",
        username="uploadstudent",
        password_hash=hash_password("StudentPass123!"),
        role="student",
    )
    create_student_profile(student_id=student.id, educator_id=educator.id, grade_level=6, class_number=601)
    return educator, student


def test_upload_creates_record_and_queues_job(
    client, monkeypatch, educator_and_student
) -> None:
    _educator, student = educator_and_student

    fake_s3 = _FakeS3Client()
    def fake_boto_client(service_name: str, **kwargs):
        if service_name == "s3":
            return fake_s3
        raise AssertionError(f"Unsupported service: {service_name}")

    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "test-bucket")
    monkeypatch.setattr("boto3.client", fake_boto_client)

    enqueued_ids: list[int] = []

    def fake_enqueue(upload_id: int) -> None:
        enqueued_ids.append(upload_id)

    monkeypatch.setattr("app.routes.enqueue_upload_job", fake_enqueue)

    _login_as_educator(client, "uploadteacher", "TeacherPass123!")

    data = {
        "student_id": str(student.id),
        "files": (io.BytesIO(b"hello world"), "sample.txt"),
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")

    payload = response.get_json()
    assert response.status_code == 201, payload
    assert payload is not None
    assert "results" in payload
    result = payload["results"][0]
    assert result["status"] == "pending"
    upload_id = result["upload_id"]
    assert isinstance(upload_id, int)

    assert fake_s3.uploads == [("test-bucket", result["file_path"].split("/", 3)[-1])]
    assert enqueued_ids == [upload_id]

    status = get_upload_status(upload_id)
    assert status == "pending"

    status_response = client.get(f"/api/job-status/{upload_id}")
    assert status_response.status_code == 200
    assert status_response.get_json() == {"upload_id": upload_id, "status": "pending"}


def test_upload_rejects_invalid_extension(client, monkeypatch, educator_and_student) -> None:
    _educator, student = educator_and_student

    fake_s3 = _FakeS3Client()

    def fake_boto_client(service_name: str, **kwargs):
        if service_name == "s3":
            return fake_s3
        raise AssertionError(f"Unsupported service: {service_name}")

    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "test-bucket")
    monkeypatch.setattr("boto3.client", fake_boto_client)

    _login_as_educator(client, "uploadteacher", "TeacherPass123!")

    data = {
        "student_id": str(student.id),
        "files": (io.BytesIO(b"bad"), "malware.exe"),
    }
    response = client.post("/api/upload", data=data, content_type="multipart/form-data")
    payload = response.get_json()
    assert response.status_code == 400
    assert payload["results"][0]["error"].startswith("Unsupported file type")
    assert fake_s3.uploads == []


def test_job_status_not_found_returns_404(client, monkeypatch, educator_and_student) -> None:
    _educator, _student = educator_and_student
    _login_as_educator(client, "uploadteacher", "TeacherPass123!")

    response = client.get("/api/job-status/999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Upload not found."}

