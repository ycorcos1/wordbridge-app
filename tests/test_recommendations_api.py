from __future__ import annotations

import datetime
from collections.abc import Iterator

import pytest

from app.security import hash_password
from models import (
    create_recommendations,
    create_student_profile,
    create_upload_record,
    create_user,
    get_connection,
    list_recommendations_for_upload,
)


def _login(client, identifier: str, password: str, role: str = "educator") -> None:
    response = client.post(
        "/login",
        data={"identifier": identifier, "password": password, "role": role},
        follow_redirects=False,
    )
    assert response.status_code == 302


def _set_recommendation_created_at(recommendation_id: int, timestamp: datetime.datetime):
    conn = get_connection()
    cur = conn.cursor()
    try:
        if conn.__class__.__module__.startswith("sqlite3"):
            cur.execute(
                "UPDATE recommendations SET created_at = ? WHERE id = ?",
                (timestamp, recommendation_id),
            )
        else:
            cur.execute(
                "UPDATE recommendations SET created_at = %s WHERE id = %s",
                (timestamp, recommendation_id),
            )
        conn.commit()
    finally:
        cur.close()


def _hash(password: str) -> str:
    return hash_password(password)


@pytest.fixture()
def recommendations_context(app_context) -> Iterator[dict[str, object]]:
    educator_password = "TeachPass123!"
    student_password = "StudentPass123!"

    educator = create_user(
        name="Review Teacher",
        email="review.teacher@example.com",
        username="review_teacher",
        password_hash=_hash(educator_password),
        role="educator",
    )

    student_one = create_user(
        name="Student Alpha",
        email="student.alpha@example.com",
        username="student_alpha",
        password_hash=_hash(student_password),
        role="student",
    )
    create_student_profile(
        student_id=student_one.id,
        educator_id=educator.id,
        grade_level=6,
        class_number=601,
    )

    student_two = create_user(
        name="Student Beta",
        email="student.beta@example.com",
        username="student_beta",
        password_hash=_hash(student_password),
        role="student",
    )
    create_student_profile(
        student_id=student_two.id,
        educator_id=educator.id,
        grade_level=7,
        class_number=701,
    )

    upload_one = create_upload_record(
        educator_id=educator.id,
        student_id=student_one.id,
        file_path="/tmp/upload_one.txt",
        filename="upload_one.txt",
        status="completed",
    )
    upload_two = create_upload_record(
        educator_id=educator.id,
        student_id=student_two.id,
        file_path="/tmp/upload_two.txt",
        filename="upload_two.txt",
        status="completed",
    )

    create_recommendations(
        student_id=student_one.id,
        upload_id=upload_one,
        records=[
            {
                "word": "Alpha",
                "definition": "Definition alpha",
                "rationale": "Rationale alpha",
                "difficulty_score": 4,
                "example_sentence": "Example alpha.",
                "status": "pending",
            },
            {
                "word": "Beta",
                "definition": "Definition beta",
                "rationale": "Rationale beta",
                "difficulty_score": 5,
                "example_sentence": "Example beta.",
                "status": "approved",
            },
            {
                "word": "Gamma",
                "definition": "Definition gamma",
                "rationale": "Rationale gamma",
                "difficulty_score": 6,
                "example_sentence": "Example gamma.",
                "status": "rejected",
            },
        ],
    )

    create_recommendations(
        student_id=student_two.id,
        upload_id=upload_two,
        records=[
            {
                "word": "Delta",
                "definition": "Definition delta",
                "rationale": "Rationale delta",
                "difficulty_score": 7,
                "example_sentence": "Example delta.",
                "status": "pending",
            },
            {
                "word": "Epsilon",
                "definition": "Definition epsilon",
                "rationale": "Rationale epsilon",
                "difficulty_score": 3,
                "example_sentence": "Example epsilon.",
                "status": "pending",
            },
        ],
    )

    recs_one = list_recommendations_for_upload(upload_one)
    recs_two = list_recommendations_for_upload(upload_two)

    all_recommendations: dict[str, dict[str, object]] = {}
    for entry in recs_one + recs_two:
        all_recommendations[entry["word"]] = entry

    _set_recommendation_created_at(
        all_recommendations["Alpha"]["id"], datetime.datetime(2025, 1, 2, 9, 0, 0)
    )
    _set_recommendation_created_at(
        all_recommendations["Beta"]["id"], datetime.datetime(2025, 1, 1, 9, 0, 0)
    )
    _set_recommendation_created_at(
        all_recommendations["Gamma"]["id"], datetime.datetime(2025, 1, 5, 12, 0, 0)
    )
    _set_recommendation_created_at(
        all_recommendations["Delta"]["id"], datetime.datetime(2025, 1, 3, 10, 0, 0)
    )
    _set_recommendation_created_at(
        all_recommendations["Epsilon"]["id"], datetime.datetime(2025, 1, 6, 15, 30, 0)
    )

    other_educator = create_user(
        name="Other Teacher",
        email="other.teacher@example.com",
        username="other_teacher",
        password_hash=_hash("OtherTeach123!"),
        role="educator",
    )
    other_student = create_user(
        name="Other Student",
        email="other.student@example.com",
        username="other_student",
        password_hash=_hash("OtherStudent123!"),
        role="student",
    )
    create_student_profile(
        student_id=other_student.id,
        educator_id=other_educator.id,
        grade_level=8,
        class_number=801,
    )
    other_upload = create_upload_record(
        educator_id=other_educator.id,
        student_id=other_student.id,
        file_path="/tmp/upload_other.txt",
        filename="upload_other.txt",
        status="completed",
    )
    create_recommendations(
        student_id=other_student.id,
        upload_id=other_upload,
        records=[
            {
                "word": "Zeta",
                "definition": "Definition zeta",
                "rationale": "Rationale zeta",
                "difficulty_score": 5,
                "example_sentence": "Example zeta.",
                "status": "pending",
            }
        ],
    )
    other_rec = list_recommendations_for_upload(other_upload)[0]

    yield {
        "educator": educator,
        "educator_password": educator_password,
        "students": {"one": student_one, "two": student_two},
        "student_password": student_password,
        "recommendations": all_recommendations,
        "other_recommendation": other_rec,
    }


def test_list_recommendations_default_pending(client, recommendations_context):
    ctx = recommendations_context
    _login(client, ctx["educator"].username, ctx["educator_password"])

    response = client.get("/api/recommendations")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["total"] == 3
    words = {item["word"] for item in payload["items"]}
    assert words == {"Alpha", "Delta", "Epsilon"}


def test_list_recommendations_with_filters(client, recommendations_context):
    ctx = recommendations_context
    _login(client, ctx["educator"].username, ctx["educator_password"])
    student_one = ctx["students"]["one"]

    response = client.get(
        "/api/recommendations",
        query_string={
            "student_id": student_one.id,
            "difficulty_min": 5,
            "status": "all",
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    words = {item["word"] for item in payload["items"]}
    assert words == {"Beta", "Gamma"}

    response_dates = client.get(
        "/api/recommendations",
        query_string={
            "status": "all",
            "date_from": "2025-01-05",
        },
    )
    assert response_dates.status_code == 200
    date_payload = response_dates.get_json()
    date_words = {item["word"] for item in date_payload["items"]}
    assert date_words == {"Gamma", "Epsilon"}


def test_bulk_status_updates_scoped(client, recommendations_context):
    ctx = recommendations_context
    _login(client, ctx["educator"].username, ctx["educator_password"])
    recs = ctx["recommendations"]

    approve_response = client.post(
        "/api/recommendations/approve",
        json={"ids": [recs["Alpha"]["id"], recs["Delta"]["id"]]},
    )
    assert approve_response.status_code == 200
    assert approve_response.get_json()["updated"] == 2

    reject_response = client.post(
        "/api/recommendations/reject", json={"ids": [recs["Epsilon"]["id"]]}
    )
    assert reject_response.status_code == 200
    assert reject_response.get_json()["updated"] == 1

    # Attempt to modify recommendation not owned by educator → 404
    forbidden_response = client.post(
        "/api/recommendations/approve",
        json={"ids": [ctx["other_recommendation"]["id"]]},
    )
    assert forbidden_response.status_code == 404

    # After updates only approved/rejected results remain for pending filter
    remaining_response = client.get("/api/recommendations")
    assert remaining_response.status_code == 200
    remaining_payload = remaining_response.get_json()
    assert remaining_payload["total"] == 0


def test_edit_rationale_validation_and_update(client, recommendations_context):
    ctx = recommendations_context
    _login(client, ctx["educator"].username, ctx["educator_password"])
    recs = ctx["recommendations"]

    bad_response = client.post(
        "/api/recommendations/edit",
        json={"id": recs["Gamma"]["id"], "rationale": "   "},
    )
    assert bad_response.status_code == 400

    updated_response = client.post(
        "/api/recommendations/edit",
        json={"id": recs["Gamma"]["id"], "rationale": "Updated rationale text"},
    )
    assert updated_response.status_code == 200
    assert updated_response.get_json()["updated"] is True

    verify_response = client.get(
        "/api/recommendations",
        query_string={"status": "all", "student_id": ctx["students"]["one"].id},
    )
    payload = verify_response.get_json()
    gamma_entry = next(item for item in payload["items"] if item["word"] == "Gamma")
    assert gamma_entry["rationale"] == "Updated rationale text"


def test_pin_toggle(client, recommendations_context):
    ctx = recommendations_context
    _login(client, ctx["educator"].username, ctx["educator_password"])
    recs = ctx["recommendations"]

    pin_response = client.post(
        "/api/recommendations/pin", json={"id": recs["Alpha"]["id"], "pinned": True}
    )
    assert pin_response.status_code == 200
    assert pin_response.get_json()["pinned"] is True

    unpin_response = client.post(
        "/api/recommendations/pin", json={"id": recs["Alpha"]["id"], "pinned": False}
    )
    assert unpin_response.status_code == 200
    assert unpin_response.get_json()["pinned"] is False


def test_student_access_forbidden(client, recommendations_context):
    ctx = recommendations_context
    student = ctx["students"]["one"]
    _login(client, student.username, ctx["student_password"], role="student")

    response = client.get("/api/recommendations")
    assert response.status_code == 403


def test_invalid_query_parameters_return_400(client, recommendations_context):
    ctx = recommendations_context
    _login(client, ctx["educator"].username, ctx["educator_password"])

    bad_response = client.get(
        "/api/recommendations",
        query_string={"difficulty_min": "not-a-number"},
    )
    assert bad_response.status_code == 400

    bad_payload = client.post("/api/recommendations/approve", json={"ids": []})
    assert bad_payload.status_code == 400

    bad_pin = client.post(
        "/api/recommendations/pin",
        json={"id": ctx["recommendations"]["Alpha"]["id"], "pinned": "maybe"},
    )
    assert bad_pin.status_code == 400

