"""Basic performance and load tests."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest


@pytest.mark.perf
def test_concurrent_health_checks(app):
    """Verify health endpoint handles concurrent requests without errors."""
    num_requests = 50
    timeout_seconds = 10

    def make_request():
        # Create a new test client for each thread to avoid context issues
        with app.test_client() as thread_client:
            response = thread_client.get("/health")
            return response.status_code, response.get_json()

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(num_requests)]
        results = []
        for future in as_completed(futures, timeout=timeout_seconds):
            try:
                status_code, payload = future.result()
                results.append((status_code, payload))
            except Exception as e:
                pytest.fail(f"Request failed with exception: {e}")

    elapsed = time.time() - start_time

    # Verify all requests succeeded
    assert len(results) == num_requests
    for status_code, payload in results:
        assert status_code == 200
        assert payload is not None
        assert payload.get("status") == "ok"

    # Verify reasonable performance (all requests complete within timeout)
    assert elapsed < timeout_seconds
    avg_time = elapsed / num_requests
    # Average response time should be reasonable (< 100ms per request)
    assert avg_time < 0.1, f"Average response time {avg_time:.3f}s exceeds 100ms"


@pytest.mark.perf
def test_concurrent_index_requests(app):
    """Verify index route handles concurrent requests without errors."""
    num_requests = 30

    def make_request():
        # Create a new test client for each thread to avoid context issues
        with app.test_client() as thread_client:
            response = thread_client.get("/")
            return response.status_code

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request) for _ in range(num_requests)]
        results = []
        for future in as_completed(futures, timeout=5):
            try:
                status_code = future.result()
                results.append(status_code)
            except Exception as e:
                pytest.fail(f"Request failed with exception: {e}")

    # Verify all requests succeeded (200 or redirect)
    assert len(results) == num_requests
    for status_code in results:
        assert status_code in (200, 302), f"Unexpected status code: {status_code}"


@pytest.mark.perf
def test_worker_processing_time(monkeypatch, app_context):
    """Verify worker processes uploads within reasonable time bounds."""
    from app.jobs.worker import process_upload_job
    from models import create_user, create_student_profile, create_upload_record
    from app.security import hash_password
    import uuid

    def _unique(label: str) -> str:
        return f"{label}_{uuid.uuid4().hex[:8]}"

    class _FakeS3Client:
        def __init__(self):
            self.files: dict[str, bytes] = {}

        def download_fileobj(self, bucket: str, key: str, fileobj) -> None:
            content = self.files.get(f"{bucket}/{key}", b"")
            fileobj.write(content)
            fileobj.seek(0)

    fake_s3 = _FakeS3Client()

    def fake_boto_client(service_name: str, **kwargs):
        if service_name == "s3":
            return fake_s3
        raise AssertionError(f"Unsupported service: {service_name}")

    monkeypatch.setattr("boto3.client", fake_boto_client)
    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "test-bucket")

    # Mock OpenAI to return quickly with 5 recommendations (using safe words that pass content filter)
    def mock_openai(*args, **kwargs):
        import json
        recommendations = [
            {
                "word": "analyze",
                "definition": "Examine something carefully to understand it.",
                "rationale": "The student would benefit from using this word in their writing.",
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
        return json.dumps({"recommendations": recommendations})

    monkeypatch.setattr(
        "app.services.openai_client.generate_json_response",
        mock_openai,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    # Create test data
    educator = create_user(
        name="Perf Test Educator",
        email=f"{_unique('perf')}@example.com",
        username=_unique("perf_educator"),
        password_hash=hash_password("Password123!"),
        role="educator",
    )
    student = create_user(
        name="Perf Test Student",
        email=f"{_unique('perf_student')}@example.com",
        username=_unique("perf_student"),
        password_hash=hash_password("Password123!"),
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
    sample_text = " ".join(["Sample text for performance testing."] * 50)
    file_content = sample_text.encode("utf-8")
    s3_key = f"test-bucket/uploads/{educator.id}/{student.id}/123_perf.txt"
    fake_s3.files[s3_key] = file_content

    upload_id = create_upload_record(
        educator_id=educator.id,
        student_id=student.id,
        file_path=f"s3://{s3_key}",
        filename="perf_test.txt",
        status="pending",
    )

    # Process job and measure time
    start_time = time.time()
    result = process_upload_job(upload_id, s3_client=fake_s3)
    elapsed = time.time() - start_time

    # Verify job completed successfully
    assert result.success, f"Job failed: {result.error}"

    # Verify processing completed within reasonable time
    # With mocked OpenAI, should complete quickly (< 5 seconds)
    assert elapsed < 5.0, f"Processing took {elapsed:.2f}s, exceeds 5s threshold"

