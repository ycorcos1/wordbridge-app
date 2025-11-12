"""End-to-end tests for the complete WordBridge workflow."""
from __future__ import annotations

import io
import json
import uuid
from urllib.parse import urlparse

import pytest

from app.jobs.worker import process_upload_job
from app.services.openai_client import OpenAIResponseError
from models import (
    create_student_profile,
    create_upload_record,
    create_user,
    ensure_baseline_words_loaded,
    ensure_student_progress_row,
    get_upload_status,
    list_approved_words_for_student,
)
from app.security import hash_password


def _unique(label: str) -> str:
    """Generate a unique identifier for test data."""
    return f"{label}_{uuid.uuid4().hex[:8]}"


class _FakeS3Client:
    """Mock S3 client for testing."""

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
    """Provide a fake S3 client for testing."""
    fake = _FakeS3Client()

    def fake_boto_client(service_name: str, **kwargs):
        if service_name == "s3":
            return fake
        raise AssertionError(f"Unsupported service: {service_name}")

    monkeypatch.setattr("boto3.client", fake_boto_client)
    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "test-bucket")
    return fake


@pytest.fixture()
def mock_openai(monkeypatch):
    """Mock OpenAI client to return predictable recommendations."""
    mock_recommendations = {
        "recommendations": [
            {
                "word": "analyze",
                "definition": "Examine something carefully to understand it.",
                "rationale": "The student writes about topics that require analysis.",
                "difficulty_score": 4,
                "example_sentence": "Scientists analyze data to find patterns.",
            },
            {
                "word": "evaluate",
                "definition": "Judge or determine the value of something.",
                "rationale": "This word would enhance the student's critical thinking vocabulary.",
                "difficulty_score": 5,
                "example_sentence": "Teachers evaluate student work to provide feedback.",
            },
            {
                "word": "synthesize",
                "definition": "Combine parts to form a whole.",
                "rationale": "The student's writing shows readiness for synthesis concepts.",
                "difficulty_score": 6,
                "example_sentence": "Students synthesize information from multiple sources.",
            },
            {
                "word": "context",
                "definition": "The surrounding information that helps explain meaning.",
                "rationale": "Understanding context is crucial for reading comprehension.",
                "difficulty_score": 3,
                "example_sentence": "The context of the story helps us understand the character.",
            },
            {
                "word": "interpret",
                "definition": "Explain the meaning of information or actions.",
                "rationale": "The student would benefit from using this word in their writing.",
                "difficulty_score": 5,
                "example_sentence": "We interpret the results to understand what happened.",
            },
        ]
    }

    def mock_generate_json_response(messages, *, model="gpt-4o-mini", temperature=0.4):
        return json.dumps(mock_recommendations)

    monkeypatch.setattr(
        "app.services.openai_client.generate_json_response",
        mock_generate_json_response,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


@pytest.mark.e2e
def test_complete_workflow_educator_to_student_quiz(
    client, app_context, fake_s3_client, mock_openai
):
    """Test the complete workflow: educator signup → students → upload → AI → approval → quiz."""
    ensure_baseline_words_loaded()

    # Step 1: Educator signup
    educator_username = _unique("e2e_teacher")
    signup_response = client.post(
        "/signup",
        data={
            "name": "Ms. E2E Teacher",
            "username": educator_username,
            "email": f"{educator_username}@example.com",
            "password": "TeacherPass123!",
            "confirm_password": "TeacherPass123!",
        },
        follow_redirects=True,
    )
    # Signup redirects to login on success
    assert signup_response.status_code in (200, 302)
    body = signup_response.get_data(as_text=True)
    assert "created successfully" in body.lower() or "log in" in body.lower() or signup_response.status_code == 302

    # Step 2: Educator login
    login_response = client.post(
        "/login",
        data={
            "identifier": educator_username,
            "password": "TeacherPass123!",
            "role": "educator",
        },
    )
    assert login_response.status_code == 302
    location = urlparse(login_response.headers["Location"]).path
    assert location == "/educator/dashboard"

    # Step 3: Create 3 students (one per grade)
    students = []
    for grade in [6, 7, 8]:
        student_data = {
            "name": f"Student Grade {grade}",
            "username": _unique(f"student_grade{grade}"),
            "email": f"{_unique('student')}@example.com",
            "password": "StudentPass123!",
            "grade": str(grade),
            "class_number": grade * 100 + 1,  # 601, 701, 801
        }
        create_response = client.post("/api/students/create", json=student_data)
        assert create_response.status_code == 201
        payload = create_response.get_json()
        assert payload["grade_level"] == grade
        students.append(payload)

    # Step 4: Upload a text file for the first student
    student_id = students[0]["id"]
    sample_text = " ".join(["This is a sample essay about science."] * 50)  # ~200 words
    file_content = sample_text.encode("utf-8")

    upload_response = client.post(
        "/api/upload",
        data={
            "student_id": str(student_id),
            "files": (io.BytesIO(file_content), "sample_essay.txt"),
        },
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201
    upload_payload = upload_response.get_json()
    assert "results" in upload_payload
    upload_result = upload_payload["results"][0]
    upload_id = upload_result["upload_id"]
    assert upload_result["status"] == "pending"

    # Step 5: Process the upload job (simulate worker)
    result = process_upload_job(upload_id, s3_client=fake_s3_client)
    assert result.success, f"Upload processing failed: {result.error}"

    # Verify upload status updated
    status = get_upload_status(upload_id)
    assert status == "completed"

    # Step 6: Educator views recommendations
    recommendations_response = client.get("/api/recommendations")
    assert recommendations_response.status_code == 200
    recs_payload = recommendations_response.get_json()
    assert "items" in recs_payload
    recommendations = recs_payload["items"]
    assert len(recommendations) >= 5  # Should have at least 5 recommendations

    # Filter recommendations for our student
    student_recs = [r for r in recommendations if r["student_id"] == student_id]
    assert len(student_recs) >= 5

    # Step 7: Educator approves recommendations
    rec_ids = [r["id"] for r in student_recs[:5]]  # Approve first 5
    approve_response = client.post(
        "/api/recommendations/approve",
        json={"ids": rec_ids},
    )
    assert approve_response.status_code == 200
    approve_payload = approve_response.get_json()
    assert approve_payload["updated"] == 5

    # Step 8: Logout educator and login as student
    client.get("/logout")
    student_username = students[0]["username"]
    student_login_response = client.post(
        "/login",
        data={
            "identifier": student_username,
            "password": "StudentPass123!",
            "role": "student",
        },
    )
    assert student_login_response.status_code == 302
    student_location = urlparse(student_login_response.headers["Location"]).path
    assert student_location == "/student/dashboard"

    # Step 9: Student views dashboard with approved words
    dashboard_response = client.get("/api/student/dashboard")
    assert dashboard_response.status_code == 200
    dashboard_payload = dashboard_response.get_json()
    assert "approved_words" in dashboard_payload
    approved_words = dashboard_payload["approved_words"]
    assert len(approved_words) == 5
    assert dashboard_payload["can_start_quiz"] is True

    # Step 10: Student generates quiz
    quiz_generate_response = client.get("/api/quiz/generate?count=5")
    assert quiz_generate_response.status_code == 200
    quiz_payload = quiz_generate_response.get_json()
    assert "questions" in quiz_payload
    questions = quiz_payload["questions"]
    assert len(questions) == 5

    # Step 11: Student submits quiz answers
    answers = []
    for idx, question in enumerate(questions):
        word_id = question["word_id"]
        # Answer correctly for first 3, incorrectly for last 2
        if idx < 3:
            answers.append({"word_id": word_id, "answer": question["correct_definition"]})
        else:
            answers.append({"word_id": word_id, "answer": "wrong answer"})

    quiz_submit_response = client.post("/api/quiz/submit", json={"answers": answers})
    assert quiz_submit_response.status_code == 200
    submit_payload = quiz_submit_response.get_json()
    assert submit_payload["correct"] == 3
    assert submit_payload["total"] == 5
    assert submit_payload["xp_earned"] >= 30  # 3 correct * 10 XP
    assert "progress" in submit_payload
    assert submit_payload["progress"]["xp"] > 0
    assert submit_payload["progress"]["streak_count"] == 1

    # Step 12: Verify student progress persisted
    ensure_student_progress_row(student_id)
    final_dashboard = client.get("/api/student/dashboard")
    final_payload = final_dashboard.get_json()
    assert final_payload["progress"]["xp"] > 0
    assert final_payload["progress"]["streak_count"] == 1

    # Verify word mastery was updated
    approved_words_final = list_approved_words_for_student(student_id)
    assert len(approved_words_final) == 5
    # Check that mastery data exists for words that were answered correctly
    mastery_data = final_payload.get("mastery", [])
    assert len(mastery_data) > 0


@pytest.mark.e2e
def test_multiple_students_workflow(client, app_context, fake_s3_client, mock_openai):
    """Test workflow with multiple students across different grades."""
    ensure_baseline_words_loaded()

    # Create educator
    educator = create_user(
        name="Multi-Student Teacher",
        email=f"{_unique('multi_teacher')}@example.com",
        username=_unique("multi_teacher"),
        password_hash=hash_password("TeacherPass123!"),
        role="educator",
    )

    # Login as educator
    login_response = client.post(
        "/login",
        data={
            "identifier": educator.username,
            "password": "TeacherPass123!",
            "role": "educator",
        },
    )
    assert login_response.status_code == 302

    # Create students for each grade
    students_by_grade = {}
    for grade in [6, 7, 8]:
        student = create_user(
            name=f"Grade {grade} Student",
            email=f"{_unique('student')}@example.com",
            username=_unique(f"grade{grade}_student"),
            password_hash=hash_password("StudentPass123!"),
            role="student",
        )
        create_student_profile(
            student_id=student.id,
            educator_id=educator.id,
            grade_level=grade,
            class_number=grade * 100 + 1,  # 601, 701, 801
            vocabulary_level=450 + (grade - 6) * 100,
        )
        students_by_grade[grade] = student

    # Upload files for each student
    upload_ids = []
    for grade, student in students_by_grade.items():
        sample_text = " ".join([f"Grade {grade} student writing sample."] * 50)
        file_content = sample_text.encode("utf-8")

        upload_response = client.post(
            "/api/upload",
            data={
                "student_id": str(student.id),
                "files": (io.BytesIO(file_content), f"grade{grade}_essay.txt"),
            },
            content_type="multipart/form-data",
        )
        assert upload_response.status_code == 201
        upload_payload = upload_response.get_json()
        upload_id = upload_payload["results"][0]["upload_id"]
        upload_ids.append(upload_id)

    # Process all uploads
    for upload_id in upload_ids:
        result = process_upload_job(upload_id, s3_client=fake_s3_client)
        assert result.success

    # Verify recommendations exist for all students
    recommendations_response = client.get("/api/recommendations")
    assert recommendations_response.status_code == 200
    recs_payload = recommendations_response.get_json()
    recommendations = recs_payload["items"]

    # Group by student
    recs_by_student = {}
    for rec in recommendations:
        sid = rec["student_id"]
        if sid not in recs_by_student:
            recs_by_student[sid] = []
        recs_by_student[sid].append(rec)

    # Verify each student has recommendations
    for student in students_by_grade.values():
        assert student.id in recs_by_student
        assert len(recs_by_student[student.id]) >= 5

