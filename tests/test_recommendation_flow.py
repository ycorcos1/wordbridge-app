from __future__ import annotations

import datetime
import io
import json
from pathlib import Path

import pytest

from app.jobs.worker import process_upload_job
from app.repositories import student_profiles_repo
from app.services import openai_client
from models import (
    create_student_profile,
    create_upload_record,
    create_user,
    get_upload_status,
    list_recommendations_for_upload,
)

from app.security import hash_password


def _generate_text(word_count: int) -> str:
    words = []
    for index in range(word_count):
        words.append(f"word{index % 20}")
    return " ".join(words)


@pytest.fixture()
def educator_and_student_ids(app_context):
    educator = create_user(
        name="AI Teacher",
        email="ai.teacher@example.com",
        username="aiteacher",
        password_hash=hash_password("TeacherPass123!"),
        role="educator",
    )
    student = create_user(
        name="AI Student",
        email="ai.student@example.com",
        username="aistudent",
        password_hash=hash_password("StudentPass123!"),
        role="student",
    )
    create_student_profile(student_id=student.id, educator_id=educator.id, grade_level=6, class_number=601)
    return educator.id, student.id


def test_process_upload_generates_recommendations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, educator_and_student_ids
) -> None:
    educator_id, student_id = educator_and_student_ids

    sample_text = _generate_text(220)
    file_path = tmp_path / "sample.txt"
    file_path.write_text(sample_text, encoding="utf-8")

    upload_id = create_upload_record(
        educator_id=educator_id,
        student_id=student_id,
        file_path=str(file_path),
        filename="sample.txt",
        status="pending",
    )

    fake_recommendations = {
        "recommendations": [
            {
                "word": f"word{i}",
                "definition": f"Definition {i}",
                "rationale": f"Rationale {i}",
                "difficulty_score": i % 10 + 1,
                "example_sentence": f"Example sentence {i}.",
            }
            for i in range(1, 6)
        ]
    }

    monkeypatch.setenv("CONTENT_FILTER_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_generate_json_response(messages, *, model: str, temperature: float):
        return json.dumps(fake_recommendations)

    monkeypatch.setattr(
        openai_client, "generate_json_response", fake_generate_json_response
    )

    result = process_upload_job(
        upload_id,
        s3_client=None,
        now=datetime.datetime(2024, 1, 1, 12, 0, 0),
    )
    assert result.success

    status = get_upload_status(upload_id)
    assert status == "completed"

    stored = list_recommendations_for_upload(upload_id)
    assert len(stored) == 5
    assert all(entry["status"] == "pending" for entry in stored)

    profile = student_profiles_repo.fetch_profile(student_id)
    assert profile is not None
    assert profile.get("last_analyzed_at") is not None

