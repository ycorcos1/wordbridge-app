from __future__ import annotations

import datetime
from urllib.parse import urlparse

import pytest

from app.security import hash_password
from models import (
    create_recommendations,
    create_student_profile,
    create_upload_record,
    create_user,
    ensure_student_progress_row,
    get_connection,
    list_approved_words_for_student,
)


def _login_student(client, identifier: str, password: str) -> None:
    response = client.post(
        "/login",
        data={
            "identifier": identifier,
            "password": password,
            "role": "student",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert urlparse(response.headers["Location"]).path == "/student/dashboard"


@pytest.fixture()
def student_dashboard_data(app_context):
    educator = create_user(
        name="Educator Example",
        email="dashboard_teacher@example.com",
        username="dashboard_teacher",
        password_hash=hash_password("TeachPass123!"),
        role="educator",
    )
    student_password = "StudentPass123!"
    student = create_user(
        name="Student Example",
        email="student_dashboard@example.com",
        username="student_dashboard",
        password_hash=hash_password(student_password),
        role="student",
    )
    create_student_profile(
        student_id=student.id,
        educator_id=educator.id,
        grade_level=7,
        class_number=701,
        vocabulary_level=640,
    )

    ensure_student_progress_row(student.id)
    conn = get_connection()
    cur = conn.cursor()
    last_quiz_time = datetime.datetime(2024, 1, 5, 15, 0, 0)
    badge_time = datetime.datetime(2024, 1, 2, 10, 0, 0)
    try:
        if conn.__class__.__module__.startswith("sqlite3"):
            cur.execute(
                "UPDATE student_progress SET xp = ?, streak_count = ?, last_quiz_at = ? WHERE student_id = ?",
                (1250, 4, last_quiz_time, student.id),
            )
            cur.execute(
                "INSERT INTO badges (student_id, badge_type, earned_at) VALUES (?, ?, ?)",
                (student.id, "10_words", badge_time),
            )
        else:
            cur.execute(
                "UPDATE student_progress SET xp = %s, streak_count = %s, last_quiz_at = %s WHERE student_id = %s",
                (1250, 4, last_quiz_time, student.id),
            )
            cur.execute(
                "INSERT INTO badges (student_id, badge_type, earned_at) VALUES (%s, %s, %s)",
                (student.id, "10_words", badge_time),
            )
        conn.commit()
    finally:
        cur.close()

    upload_id = create_upload_record(
        educator_id=educator.id,
        student_id=student.id,
        file_path="/tmp/dashboard_sample.txt",
        filename="dashboard_sample.txt",
        status="completed",
    )
    create_recommendations(
        student_id=student.id,
        upload_id=upload_id,
        records=[
            {
                "word": "analyze",
                "definition": "Examine something in detail to understand it better.",
                "rationale": "Appears frequently in science writing but not used by the student.",
                "difficulty_score": 3,
                "example_sentence": "Scientists analyze results to draw conclusions.",
                "status": "approved",
                "pinned": True,
            },
            {
                "word": "hypothesis",
                "definition": "An idea that can be tested to explain a fact or event.",
                "rationale": "Supports science-themed essays the student enjoys writing.",
                "difficulty_score": 5,
                "example_sentence": "Write a hypothesis before you begin your experiment.",
                "status": "approved",
            },
            {
                "word": "interpret",
                "definition": "Explain the meaning of information or actions.",
                "rationale": "Builds on the student's interest in historical narratives.",
                "difficulty_score": 4,
                "example_sentence": "Interpret the graph to describe the trend.",
                "status": "approved",
            },
            {
                "word": "synthesize",
                "definition": "Combine parts to form a new whole.",
                "rationale": "Encourages connecting ideas across subjects.",
                "difficulty_score": 6,
                "example_sentence": "Synthesize the main ideas into a summary paragraph.",
                "status": "approved",
            },
            {
                "word": "nuance",
                "definition": "A small or subtle difference in meaning or expression.",
                "rationale": "Helps develop more precise writing.",
                "difficulty_score": 7,
                "example_sentence": "Notice the nuance in the author's word choice.",
                "status": "approved",
            },
        ],
    )

    approved_words = list_approved_words_for_student(student.id)
    mastery_entries = [
        {
            "word_id": approved_words[0]["id"],
            "mastery_stage": "practicing",
            "correct_count": 1,
            "last_practiced_at": datetime.datetime(2024, 1, 6, 9, 0, 0),
        },
        {
            "word_id": approved_words[1]["id"],
            "mastery_stage": "nearly_mastered",
            "correct_count": 2,
            "last_practiced_at": datetime.datetime(2024, 1, 7, 9, 0, 0),
        },
    ]
    conn = get_connection()
    cur = conn.cursor()
    try:
        for entry in mastery_entries:
            if conn.__class__.__module__.startswith("sqlite3"):
                cur.execute(
                    "INSERT INTO word_mastery (student_id, word_id, mastery_stage, correct_count, last_practiced_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        student.id,
                        entry["word_id"],
                        entry["mastery_stage"],
                        entry["correct_count"],
                        entry["last_practiced_at"],
                    ),
                )
            else:
                cur.execute(
                    "INSERT INTO word_mastery (student_id, word_id, mastery_stage, correct_count, last_practiced_at) VALUES (%s, %s, %s, %s, %s)",
                    (
                        student.id,
                        entry["word_id"],
                        entry["mastery_stage"],
                        entry["correct_count"],
                        entry["last_practiced_at"],
                    ),
                )
        conn.commit()
    finally:
        cur.close()

    return {
        "student": student,
        "student_password": student_password,
    }


def test_student_dashboard_api_returns_expected_payload(
    client,
    student_dashboard_data,
):
    student = student_dashboard_data["student"]
    password = student_dashboard_data["student_password"]
    _login_student(client, student.username, password)

    response = client.get("/api/student/dashboard")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["can_start_quiz"] is True

    progress = payload["progress"]
    assert progress["xp"] == 1250
    assert progress["level"] == 2
    assert progress["streak_count"] == 4
    assert "last_quiz_at" in progress and progress["last_quiz_at"].startswith("2024-01-05")

    badges = payload["badges"]
    assert len(badges) == 1
    assert badges[0]["badge_type"] == "10_words"

    approved_words = payload["approved_words"]
    assert len(approved_words) == 5
    pinned_first = approved_words[0]
    assert pinned_first["pinned"] is True
    assert pinned_first["mastery"]["correct_count"] == 1
    assert approved_words[1]["mastery"]["mastery_stage"] == "nearly_mastered"

    mastery_entries = payload["mastery"]
    assert len(mastery_entries) >= 2
    stages = {entry["mastery_stage"] for entry in mastery_entries}
    assert {"practicing", "nearly_mastered"}.issubset(stages)


def test_student_dashboard_page_renders(client, student_dashboard_data):
    student = student_dashboard_data["student"]
    password = student_dashboard_data["student_password"]
    _login_student(client, student.username, password)

    response = client.get("/student/dashboard")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Your Vocabulary Words" in body
    assert "Start Quiz" in body

