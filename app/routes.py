from __future__ import annotations

import csv
import datetime
import io
import os
import time
from functools import wraps
from typing import Callable, Optional, Sequence

import boto3
from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    Response,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename

from config.settings import get_settings
from app.jobs.queue import enqueue_upload_job
from app.repositories import (
    bulk_update_status as repo_bulk_update_status,
    list_for_educator as repo_list_recommendations,
    set_pinned as repo_set_recommendation_pinned,
    update_rationale as repo_update_recommendation_rationale,
)
from app.services.quizzes import build_quiz_questions, score_quiz_and_update
from models import (
    create_student_profile,
    create_upload_record,
    create_user,
    ensure_baseline_words_loaded,
    ensure_student_progress_row,
    get_student_overview,
    get_upload_status,
    get_upload_by_id,
    get_user_by_identifier,
    get_student_progress,
    list_students_with_stats_for_educator,
    list_students_with_stats_for_grade,
    list_students_with_stats_for_class,
    list_students_for_educator,
    count_pending_recommendations_for_educator,
    count_students_for_educator,
    list_badges_for_student,
    list_word_mastery_for_student,
    list_approved_words_for_student,
    list_uploads_for_student,
    delete_upload,
    compute_level,
)
from .security import hash_password, verify_password

bp = Blueprint("core", __name__)


@bp.get("/")
def index():
    if current_user.is_authenticated:
        target = (
            "core.educator_dashboard"
            if current_user.role == "educator"
            else "core.student_dashboard"
        )
        return redirect(url_for(target))
    return render_template("index.html")


@bp.get("/health")
def health():
    return jsonify({"status": "ok", "service": "wordbridge"}), 200


@bp.get("/favicon.ico")
def favicon():
    """Serve the favicon to prevent 404 errors."""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    return send_from_directory(static_dir, "favicon.svg", mimetype="image/svg+xml")


def role_required(expected_role: str) -> Callable:
    """Ensure the current user has the provided role."""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != expected_role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _validate_student_submission(payload: dict[str, object]) -> tuple[dict[str, object], dict[str, str]]:
    """Validate student creation inputs shared by form and API routes."""
    cleaned: dict[str, object] = {}
    errors: dict[str, str] = {}

    name = str(payload.get("name", "")).strip()
    username = str(payload.get("username", "")).strip()
    email = str(payload.get("email", "")).strip()
    password = payload.get("password", "")
    grade_raw = payload.get("grade")
    class_number_raw = payload.get("class_number")

    if isinstance(password, str):
        password_value = password
    else:
        password_value = ""

    if isinstance(grade_raw, str):
        grade_raw = grade_raw.strip()
    if isinstance(class_number_raw, str):
        class_number_raw = class_number_raw.strip()

    if not name:
        errors["name"] = "Name is required."
    if not username:
        errors["username"] = "Username is required."
    if not email:
        errors["email"] = "Email is required."
    if not password_value:
        errors["password"] = "Password is required."
    elif len(password_value) < 8:
        errors["password"] = "Password must be at least 8 characters."

    grade_level: Optional[int] = None
    if grade_raw in (None, ""):
        errors["grade"] = "Grade level is required."
    else:
        try:
            grade_level = int(grade_raw)
        except (TypeError, ValueError):
            errors["grade"] = "Grade level must be 6, 7, or 8."
        else:
            if grade_level not in {6, 7, 8}:
                errors["grade"] = "Grade level must be 6, 7, or 8."

    class_number: Optional[int] = None
    if class_number_raw in (None, ""):
        errors["class_number"] = "Class number is required."
    else:
        try:
            class_number = int(class_number_raw)
        except (TypeError, ValueError):
            errors["class_number"] = (
                "Class number must be a number like 601, 602, 701, or 801."
            )
        else:
            if class_number < 601 or class_number > 899:
                errors["class_number"] = "Class number must be between 601 and 899."
            elif grade_level is not None and class_number // 100 != grade_level:
                errors[
                    "class_number"
                ] = f"Class number must start with {grade_level} (e.g., {grade_level}01)."

    cleaned["name"] = name
    cleaned["username"] = username
    cleaned["email"] = email
    cleaned["password"] = password_value if isinstance(password_value, str) else ""
    if grade_level is not None:
        cleaned["grade_level"] = grade_level
    if class_number is not None:
        cleaned["class_number"] = class_number

    return cleaned, errors


def _initial_vocabulary_level_for_grade(grade_level: int | str | None) -> int:
    """Return the baseline vocabulary level seed for a grade."""
    mapping = {6: 450, 7: 550, 8: 650}
    try:
        grade_value = int(grade_level) if grade_level is not None else None
    except (TypeError, ValueError):
        grade_value = None
    return mapping.get(grade_value, 500)


def _parse_optional_int(
    value: object,
    field_name: str,
    *,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> Optional[int]:
    """Parse optional integer from query or JSON payload."""
    if value in (None, "", "null"):
        return None
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer.")
    if min_value is not None and result < min_value:
        raise ValueError(f"{field_name} must be ≥ {min_value}.")
    if max_value is not None and result > max_value:
        raise ValueError(f"{field_name} must be ≤ {max_value}.")
    return result


def _parse_required_int(
    value: object,
    field_name: str,
    *,
    min_value: Optional[int] = None,
) -> int:
    """Parse required integer enforcing optional minimum."""
    parsed = _parse_optional_int(value, field_name, min_value=min_value)
    if parsed is None:
        raise ValueError(f"{field_name} is required.")
    return parsed


def _parse_optional_date(value: object, field_name: str) -> Optional[datetime.datetime]:
    """Parse optional ISO-8601 date or datetime string."""
    if value in (None, "", "null"):
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value)
        except ValueError as exc:  # pragma: no cover - fromisoformat already deterministic
            raise ValueError(
                f"{field_name} must be an ISO-8601 formatted date (YYYY-MM-DD) or datetime."
            ) from exc
    raise ValueError(f"{field_name} must be an ISO-8601 formatted date.")


def _parse_id_list(ids: object, field_name: str = "ids") -> list[int]:
    """Parse list of integer identifiers."""
    if not isinstance(ids, list):
        raise ValueError(f"{field_name} must be a list of integers.")
    if not ids:
        raise ValueError(f"{field_name} cannot be empty.")
    parsed: list[int] = []
    for item in ids:
        value = _parse_required_int(item, field_name, min_value=1)
        parsed.append(value)
    return parsed


def _parse_bool(value: object, field_name: str) -> bool:
    """Parse a boolean value from payload."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    raise ValueError(f"{field_name} must be a boolean value.")


ALLOWED_UPLOAD_EXTENSIONS = {"txt", "docx", "pdf", "csv"}
MAX_UPLOAD_SIZE_MB = 10


def _allowed_upload(filename: str) -> bool:
    return (
        "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_UPLOAD_EXTENSIONS
    )


def _make_boto_client(service: str):
    settings = get_settings()
    kwargs: dict[str, str] = {}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client(service, **kwargs)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(
            url_for(
                "core.educator_dashboard"
                if current_user.role == "educator"
                else "core.student_dashboard"
            )
        )

    errors: dict[str, str] = {}
    form_data = {"identifier": "", "role": "educator"}

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()

        form_data["identifier"] = identifier
        form_data["role"] = role or "educator"

        if not identifier:
            errors["identifier"] = "Email or username is required."
        if not password:
            errors["password"] = "Password is required."
        if role not in {"educator", "student"}:
            errors["role"] = "Please choose a valid role."

        if not errors:
            user = get_user_by_identifier(identifier)
            if not user or not verify_password(password, user.password_hash):
                errors["identifier"] = "Invalid credentials. Please try again."
            elif user.role != role:
                errors["role"] = (
                    "Role mismatch. Select the role associated with this account."
                )
            else:
                login_user(user)
                flash("Welcome back to WordBridge!", "success")
                redirect_target = (
                    "core.educator_dashboard"
                    if user.role == "educator"
                    else "core.student_dashboard"
                )
                return redirect(url_for(redirect_target))

    return render_template("login.html", errors=errors, form_data=form_data)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        target = (
            "core.educator_dashboard"
            if current_user.role == "educator"
            else "core.student_dashboard"
        )
        return redirect(url_for(target))

    errors: dict[str, str] = {}
    form_data = {
        "name": "",
        "username": "",
        "email": "",
    }

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        form_data.update({"name": name, "username": username, "email": email})

        if not name:
            errors["name"] = "Name is required."
        if not username:
            errors["username"] = "Username is required."
        if not email:
            errors["email"] = "Email is required."
        if not password:
            errors["password"] = "Password is required."
        if password and len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        if confirm_password != password:
            errors["confirm_password"] = "Passwords must match."

        if not errors:
            try:
                password_hash = hash_password(password)
                create_user(
                    name=name,
                    email=email,
                    username=username,
                    password_hash=password_hash,
                    role="educator",
                )
            except ValueError as exc:
                errors["form"] = str(exc)
            else:
                flash(
                    "Educator account created successfully. You can now log in.",
                    "success",
                )
                return redirect(url_for("core.login"))

    return render_template("signup.html", errors=errors, form_data=form_data)


@bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("core.login"))


@bp.route("/educator/add-student", methods=["GET", "POST"])
@role_required("educator")
def educator_add_student():
    ensure_baseline_words_loaded()

    form_data = {
        "name": "",
        "username": "",
        "email": "",
        "grade": "6",
        "class_number": "601",
    }
    errors: dict[str, str] = {}
    success = False
    new_student = None

    if request.method == "POST":
        cleaned, errors = _validate_student_submission(request.form)

        form_data["name"] = cleaned.get("name", "")
        form_data["username"] = cleaned.get("username", "")
        form_data["email"] = cleaned.get("email", "")
        form_data["grade"] = str(request.form.get("grade", "")).strip()
        form_data["class_number"] = str(request.form.get("class_number", "")).strip()

        if not errors:
            grade_level = int(cleaned["grade_level"])
            class_number = int(cleaned["class_number"])
            try:
                student = create_user(
                    name=cleaned["name"],
                    email=cleaned["email"],
                    username=cleaned["username"],
                    password_hash=hash_password(cleaned["password"]),
                    role="student",
                )
                create_student_profile(
                    student_id=student.id,
                    educator_id=current_user.id,
                    grade_level=grade_level,
                    class_number=class_number,
                    vocabulary_level=_initial_vocabulary_level_for_grade(grade_level),
                )
            except ValueError as exc:
                message = str(exc)
                errors["form"] = message
                if "already in use" in message.lower():
                    errors.setdefault("username", message)
                    errors.setdefault("email", message)
            else:
                flash("Student account created successfully!", "success")
                success = True
                new_student = student
                form_data = {
                    "name": "",
                    "username": "",
                    "email": "",
                    "grade": str(grade_level),
                    "class_number": str(class_number),
                }

    return render_template(
        "educator_add_student.html",
        errors=errors,
        form_data=form_data,
        success=success,
        new_student=new_student,
    )


@bp.post("/api/students/create")
@role_required("educator")
def api_create_student():
    ensure_baseline_words_loaded()

    payload = request.get_json(silent=True) or {}

    cleaned, errors = _validate_student_submission(payload)
    if errors:
        return jsonify({"errors": errors}), 400

    grade_level = int(cleaned["grade_level"])
    class_number = int(cleaned["class_number"])

    try:
        student = create_user(
            name=cleaned["name"],
            email=cleaned["email"],
            username=cleaned["username"],
            password_hash=hash_password(cleaned["password"]),
            role="student",
        )
        create_student_profile(
            student_id=student.id,
            educator_id=current_user.id,
            grade_level=grade_level,
            class_number=class_number,
            vocabulary_level=_initial_vocabulary_level_for_grade(grade_level),
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 409 if "already in use" in message.lower() else 400
        return jsonify({"error": message}), status_code

    response_payload = {
        "id": student.id,
        "username": student.username,
        "grade_level": grade_level,
        "class_number": class_number,
    }
    return jsonify(response_payload), 201


@bp.get("/educator/dashboard")
@role_required("educator")
def educator_dashboard():
    educator_id = current_user.id
    summary = {
        "total_students": count_students_for_educator(educator_id),
        "pending_recommendations": count_pending_recommendations_for_educator(
            educator_id
        ),
    }
    students_raw = list_students_with_stats_for_educator(educator_id)
    students_by_grade_and_class: dict[int, dict[int, dict[str, object]]] = {6: {}, 7: {}, 8: {}}
    for entry in students_raw:
        row = dict(entry)
        grade = row.get("grade_level")
        class_number = row.get("class_number")
        if not isinstance(grade, int) or grade not in students_by_grade_and_class:
            continue
        try:
            class_number_int = int(class_number)
        except (TypeError, ValueError):
            continue
        class_groups = students_by_grade_and_class[grade]
        bucket = class_groups.setdefault(
            class_number_int,
            {"students": [], "count": 0, "avg_proficiency": 0.0},
        )
        bucket["students"].append(
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "username": row.get("username", ""),
                "grade_level": grade,
                "class_number": class_number_int,
                "vocabulary_level": row.get("vocabulary_level"),
                "pending_words": row.get("pending_words", 0),
                "approved_words": row.get("approved_words", 0),
                "last_upload_at": row.get("last_upload_at"),
            }
        )
    for grade_groups in students_by_grade_and_class.values():
        for class_info in grade_groups.values():
            students = class_info["students"]
            class_info["count"] = len(students)
            if students:
                try:
                    total = sum(float(s.get("vocabulary_level") or 0) for s in students)
                except TypeError:
                    total = 0.0
                class_info["avg_proficiency"] = round(total / len(students), 1) if students else 0.0
            else:
                class_info["avg_proficiency"] = 0.0
    return render_template(
        "educator_dashboard.html",
        summary=summary,
        students_by_grade_and_class=students_by_grade_and_class,
        export_url=url_for("core.api_educator_export"),
    )


@bp.get("/api/educator/dashboard")
@role_required("educator")
def api_educator_dashboard():
    educator_id = current_user.id
    summary = {
        "total_students": count_students_for_educator(educator_id),
        "pending_recommendations": count_pending_recommendations_for_educator(
            educator_id
        ),
    }
    students = list_students_with_stats_for_educator(educator_id)

    def _serialize_student(entry: dict[str, object]) -> dict[str, object]:
        last_upload = entry.get("last_upload_at")
        if isinstance(last_upload, (datetime.datetime, datetime.date)):
            iso_last_upload = last_upload.isoformat()
        else:
            iso_last_upload = str(last_upload) if last_upload else None
        return {
            "id": entry.get("id"),
            "name": entry.get("name"),
            "grade_level": entry.get("grade_level"),
            "class_number": entry.get("class_number"),
            "vocabulary_level": entry.get("vocabulary_level"),
            "pending_words": entry.get("pending_words", 0),
            "approved_words": entry.get("approved_words", 0),
            "last_upload_at": iso_last_upload,
        }

    response_payload = {**summary, "students": [_serialize_student(s) for s in students]}
    return jsonify(response_payload)


@bp.get("/educator/recommendations")
@role_required("educator")
def educator_recommendations_page():
    students = list_students_for_educator(current_user.id)
    return render_template("educator_recommendations.html", students=students)


@bp.get("/api/recommendations")
@role_required("educator")
def api_list_recommendations():
    args = request.args
    try:
        student_id = _parse_optional_int(args.get("student_id"), "student_id", min_value=1)
        difficulty_min = _parse_optional_int(
            args.get("difficulty_min"),
            "difficulty_min",
            min_value=1,
            max_value=10,
        )
        difficulty_max = _parse_optional_int(
            args.get("difficulty_max"),
            "difficulty_max",
            min_value=1,
            max_value=10,
        )
        if (
            difficulty_min is not None
            and difficulty_max is not None
            and difficulty_min > difficulty_max
        ):
            raise ValueError("difficulty_min cannot be greater than difficulty_max.")

        date_from = _parse_optional_date(args.get("date_from"), "date_from")
        date_to = _parse_optional_date(args.get("date_to"), "date_to")
        if date_from and date_to and date_from > date_to:
            raise ValueError("date_from cannot be later than date_to.")

        raw_status = args.get("status")
        if raw_status is None or str(raw_status).strip() == "":
            status = "pending"
        else:
            normalized_status = str(raw_status).strip().lower()
            if normalized_status == "all":
                status = None
            elif normalized_status in {"pending", "approved", "rejected"}:
                status = normalized_status
            else:
                raise ValueError("status must be 'pending', 'approved', 'rejected', or 'all'.")

        limit = _parse_optional_int(args.get("limit"), "limit", min_value=1, max_value=200)
        offset = _parse_optional_int(args.get("offset"), "offset", min_value=0)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    limit = limit or 100
    offset = offset or 0

    data = repo_list_recommendations(
        educator_id=current_user.id,
        student_id=student_id,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        date_from=date_from,
        date_to=date_to,
        status=status,
        limit=limit,
        offset=offset,
    )

    items_payload: list[dict[str, object]] = []
    for entry in data.get("items", []):
        created_at = entry.get("created_at")
        created_iso: Optional[str]
        if isinstance(created_at, datetime.datetime):
            created_iso = created_at.isoformat()
        elif isinstance(created_at, datetime.date):
            created_iso = datetime.datetime.combine(
                created_at, datetime.datetime.min.time()
            ).isoformat()
        elif isinstance(created_at, str):
            try:
                created_iso = datetime.datetime.fromisoformat(created_at).isoformat()
            except ValueError:
                created_iso = created_at
        else:
            created_iso = None

        items_payload.append(
            {
                "id": entry.get("id"),
                "student_id": entry.get("student_id"),
                "student_name": entry.get("student_name"),
                "word": entry.get("word"),
                "definition": entry.get("definition"),
                "rationale": entry.get("rationale"),
                "difficulty_score": entry.get("difficulty_score"),
                "example_sentence": entry.get("example_sentence"),
                "status": entry.get("status"),
                "pinned": bool(entry.get("pinned")),
                "created_at": created_iso,
            }
        )

    total = data.get("total", len(items_payload))

    return jsonify(
        {
            "items": items_payload,
            "total": int(total or 0),
            "limit": limit,
            "offset": offset,
        }
    )


def _handle_bulk_status_update(status: str):
    payload = request.get_json(silent=True) or {}
    try:
        ids = _parse_id_list(payload.get("ids"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    updated = repo_bulk_update_status(
        educator_id=current_user.id,
        ids=ids,
        status=status,
    )
    if updated == 0:
        return jsonify({"error": "No matching recommendations found."}), 404
    return jsonify({"updated": updated})


@bp.post("/api/recommendations/approve")
@role_required("educator")
def api_recommendations_approve():
    return _handle_bulk_status_update("approved")


@bp.post("/api/recommendations/reject")
@role_required("educator")
def api_recommendations_reject():
    return _handle_bulk_status_update("rejected")


@bp.post("/api/recommendations/edit")
@role_required("educator")
def api_recommendations_edit():
    payload = request.get_json(silent=True) or {}
    try:
        recommendation_id = _parse_required_int(payload.get("id"), "id", min_value=1)
        rationale_raw = payload.get("rationale", "")
        rationale = str(rationale_raw).strip()
        if not rationale:
            raise ValueError("rationale is required.")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    updated = repo_update_recommendation_rationale(
        educator_id=current_user.id,
        recommendation_id=recommendation_id,
        rationale=rationale,
    )
    if not updated:
        return jsonify({"error": "Recommendation not found."}), 404
    return jsonify({"updated": True})


@bp.post("/api/recommendations/pin")
@role_required("educator")
def api_recommendations_pin():
    payload = request.get_json(silent=True) or {}
    try:
        recommendation_id = _parse_required_int(payload.get("id"), "id", min_value=1)
        pinned_value = _parse_bool(payload.get("pinned"), "pinned")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    updated = repo_set_recommendation_pinned(
        educator_id=current_user.id,
        recommendation_id=recommendation_id,
        pinned=pinned_value,
    )
    if not updated:
        return jsonify({"error": "Recommendation not found."}), 404
    return jsonify({"updated": True, "pinned": pinned_value})


@bp.get("/api/educator/export")
@role_required("educator")
def api_educator_export():
    educator_id = current_user.id
    students = list_students_with_stats_for_educator(educator_id)
    csv_data = _build_students_csv(students)
    response = Response(csv_data, mimetype="text/csv")
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="wordbridge_all_students_{timestamp}.csv"'
    )
    return response


@bp.get("/api/educator/export/grade/<int:grade_level>")
@role_required("educator")
def api_educator_export_grade(grade_level: int):
    """Export CSV for a specific grade level."""
    if grade_level not in {6, 7, 8}:
        return jsonify({"error": "Invalid grade level. Must be 6, 7, or 8."}), 400

    educator_id = current_user.id
    students = list_students_with_stats_for_grade(educator_id, grade_level)
    csv_data = _build_students_csv(students)

    response = Response(csv_data, mimetype="text/csv")
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="wordbridge_grade{grade_level}_{timestamp}.csv"'
    )
    return response


@bp.get("/api/educator/export/class/<int:grade_level>/<int:class_number>")
@role_required("educator")
def api_educator_export_class(grade_level: int, class_number: int):
    """Export CSV for a specific class within a grade level."""
    if grade_level not in {6, 7, 8}:
        return jsonify({"error": "Invalid grade level. Must be 6, 7, or 8."}), 400

    lower_bound = grade_level * 100 + 1
    upper_bound = grade_level * 100 + 99
    if not (lower_bound <= class_number <= upper_bound):
        return (
            jsonify(
                {
                    "error": (
                        f"Invalid class number. For grade {grade_level}, "
                        f"class number must be between {lower_bound} and {upper_bound}."
                    )
                }
            ),
            400,
        )

    educator_id = current_user.id
    students = list_students_with_stats_for_class(
        educator_id, grade_level, class_number
    )
    csv_data = _build_students_csv(students)

    response = Response(csv_data, mimetype="text/csv")
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="wordbridge_class{class_number}_{timestamp}.csv"'
    )
    return response


def _build_students_csv(students: Sequence[dict[str, object]]) -> str:
    """Return CSV string for a collection of student records."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "name",
            "grade_level",
            "class_number",
            "vocabulary_level",
            "pending_words",
            "last_upload_at",
        ]
    )

    for entry in students:
        writer.writerow(
            [
                entry.get("id"),
                _csv_safe(entry.get("name")),
                entry.get("grade_level"),
                entry.get("class_number"),
                entry.get("vocabulary_level"),
                entry.get("pending_words", 0),
                _isoformat_or_none(entry.get("last_upload_at")),
            ]
        )

    return output.getvalue()


def _csv_safe(value: object) -> object:
    """Escape values that could be interpreted as formulas by spreadsheet apps."""
    if isinstance(value, str) and value and value[0] in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value


def _isoformat_or_none(value: object) -> Optional[str]:
    if value in (None, "", "null"):
        return None
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.datetime.min.time()).isoformat()
    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value).isoformat()
        except ValueError:
            return value
    return None


@bp.get("/api/student/dashboard")
@role_required("student")
def api_student_dashboard():
    # CRITICAL: Reset database connection to ensure we're using PostgreSQL
    from models import reset_engine
    reset_engine()
    
    student_id = current_user.id
    ensure_student_progress_row(student_id)

    progress_row = get_student_progress(student_id) or {}
    xp_raw = progress_row.get("xp", 0)
    streak_raw = progress_row.get("streak_count", 0)

    try:
        xp_value = int(xp_raw)
    except (TypeError, ValueError):
        xp_value = 0

    try:
        streak_value = int(streak_raw)
    except (TypeError, ValueError):
        streak_value = 0

    level_value = compute_level(xp_value)

    progress_payload = {
        "xp": xp_value,
        "level": level_value,
        "streak_count": streak_value,
        "last_quiz_at": _isoformat_or_none(progress_row.get("last_quiz_at")),
    }

    badges_raw = list_badges_for_student(student_id)
    badges_payload: list[dict[str, object]] = []
    for entry in badges_raw:
        badges_payload.append(
            {
                "id": entry.get("id"),
                "badge_type": entry.get("badge_type"),
                "earned_at": _isoformat_or_none(entry.get("earned_at")),
            }
        )

    approved_words_raw = list_approved_words_for_student(student_id, limit=500, offset=0)
    mastery_raw = list_word_mastery_for_student(student_id)
    mastery_lookup = {entry.get("word_id"): entry for entry in mastery_raw}

    approved_words_payload: list[dict[str, object]] = []
    for entry in approved_words_raw:
        word_id = entry.get("id")
        mastery_entry = mastery_lookup.get(word_id, {})
        approved_words_payload.append(
            {
                "id": word_id,
                "word": entry.get("word"),
                "definition": entry.get("definition"),
                "rationale": entry.get("rationale"),
                "difficulty_score": entry.get("difficulty_score"),
                "example_sentence": entry.get("example_sentence"),
                "pinned": bool(entry.get("pinned")),
                "created_at": _isoformat_or_none(entry.get("created_at")),
                "mastery": {
                    "mastery_stage": mastery_entry.get("mastery_stage", "practicing"),
                    "correct_count": mastery_entry.get("correct_count", 0),
                    "last_practiced_at": _isoformat_or_none(
                        mastery_entry.get("last_practiced_at")
                    ),
                },
            }
        )

    response_payload = {
        "progress": progress_payload,
        "badges": badges_payload,
        "approved_words": approved_words_payload,
        "mastery": [
            {
                "word_id": entry.get("word_id"),
                "mastery_stage": entry.get("mastery_stage"),
                "correct_count": entry.get("correct_count"),
                "last_practiced_at": _isoformat_or_none(entry.get("last_practiced_at")),
            }
            for entry in mastery_raw
        ],
        "can_start_quiz": len(approved_words_payload) >= 5,
    }
    return jsonify(response_payload)


@bp.get("/student/dashboard")
@role_required("student")
def student_dashboard():
    return render_template("student_dashboard.html")


@bp.get("/educator/students/<username>")
@role_required("educator")
def educator_student_detail(username: str):
    from models import get_student_overview_by_username
    # CRITICAL: Reset database connection to ensure we're using PostgreSQL
    from models import reset_engine
    reset_engine()
    
    overview = get_student_overview_by_username(current_user.id, username)
    if overview is None:
        abort(404)
    
    student_id = overview["student_id"]
    
    # Fetch all uploads for this student
    uploads = list_uploads_for_student(student_id)
    
    # Fetch recommendations for this student
    recommendations_data = repo_list_recommendations(
        educator_id=current_user.id,
        student_id=student_id,
        status=None,  # Get all statuses
        limit=100,
        offset=0,
    )
    
    return render_template(
        "educator_student_detail.html", 
        overview=overview,
        uploads=uploads,
        recommendations=recommendations_data["items"],
        recommendations_total=recommendations_data["total"]
    )


@bp.get("/educator/upload")
@role_required("educator")
def educator_upload_page():
    educator_id = current_user.id
    student_id = request.args.get("student_id", type=int)
    
    students = list_students_for_educator(educator_id)
    
    # Verify student belongs to educator if student_id provided
    selected_student = None
    if student_id:
        selected_student = next(
            (s for s in students if s.get("id") == student_id), 
            None
        )
        if not selected_student:
            flash("Student not found.", "error")
            return redirect(url_for("core.educator_dashboard"))
    
    return render_template(
        "educator_upload.html",
        students=students,
        selected_student=selected_student,
        allowed_extensions=sorted(ALLOWED_UPLOAD_EXTENSIONS),
        max_size_mb=MAX_UPLOAD_SIZE_MB,
    )


@bp.post("/api/upload")
@role_required("educator")
def api_upload():
    # CRITICAL: Reset database connection to ensure we're using PostgreSQL
    # This must be done at the start of every request to prevent cached SQLite connections
    from models import reset_engine
    reset_engine()
    
    student_id_raw = request.form.get("student_id", "").strip()
    if not student_id_raw:
        return jsonify({"error": "student_id is required"}), 400

    try:
        student_id = int(student_id_raw)
    except ValueError:
        return jsonify({"error": "student_id must be an integer"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided."}), 400

    settings = get_settings()
    if not settings.AWS_S3_BUCKET_NAME:
        return (
            jsonify(
                {"error": "AWS_S3_BUCKET_NAME is not configured for this environment."}
            ),
            500,
        )

    s3_client = _make_boto_client("s3")
    results: list[dict[str, object]] = []

    for item in files:
        original_name = secure_filename(item.filename or "")
        if not original_name:
            results.append({"filename": "", "error": "Filename is required."})
            continue

        if not _allowed_upload(original_name):
            results.append(
                {
                    "filename": original_name,
                    "error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
                }
            )
            continue

        stream = item.stream
        stream.seek(0, os.SEEK_END)
        size_bytes = stream.tell()
        stream.seek(0)
        if size_bytes > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            results.append(
                {
                    "filename": original_name,
                    "error": f"File exceeds {MAX_UPLOAD_SIZE_MB}MB limit.",
                }
            )
            continue

        timestamp = int(time.time())
        s3_key = f"uploads/{current_user.id}/{student_id}/{timestamp}_{original_name}"

        try:
            s3_client.upload_fileobj(stream, settings.AWS_S3_BUCKET_NAME, s3_key)
            file_path = f"s3://{settings.AWS_S3_BUCKET_NAME}/{s3_key}"
            
            # CRITICAL: Ensure we're using the correct database before creating upload
            # Reset connection to pick up any environment changes
            from models import reset_engine, get_connection
            reset_engine()
            conn = get_connection()
            # Log which database we're using for debugging
            import logging
            logger = logging.getLogger(__name__)
            from models import _backend
            logger.info(f"Creating upload record - backend: {_backend}, connection type: {type(conn)}")
            
            upload_id = create_upload_record(
                educator_id=current_user.id,
                student_id=student_id,
                file_path=file_path,
                filename=original_name,
                status="pending",
            )
            
            # Enqueue MUST succeed - if it fails, we need to know about it
            import logging
            logger = logging.getLogger(__name__)
            try:
                enqueue_upload_job(upload_id)
                logger.info(f"Successfully enqueued upload job {upload_id} for file {original_name} (student {student_id})")
            except Exception as enqueue_error:
                logger.error(f"CRITICAL: Failed to enqueue upload job {upload_id} for file {original_name}: {enqueue_error}", exc_info=True)
                # Don't fail the upload - let the recovery function pick it up
                # But log it so we know there's an issue
                logger.warning(f"Upload {upload_id} created but not enqueued. Recovery function will pick it up within 1 minute.")

            results.append(
                {
                    "filename": original_name,
                    "upload_id": upload_id,
                    "status": "pending",
                    "file_path": file_path,
                }
            )
        except Exception as exc:  # pragma: no cover - network or boto errors
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing upload {original_name}: {exc}", exc_info=True)
            results.append({"filename": original_name, "error": str(exc)})

    successful = [entry for entry in results if "upload_id" in entry]
    if not successful:
        return jsonify({"results": results}), 400
    status_code = 207 if len(successful) != len(results) else 201
    
    # Add redirect URL and success message for successful uploads
    # Get student username for the redirect URL
    from models import get_student_profile
    student_profile = get_student_profile(student_id)
    student_username = student_profile.get("username") if student_profile else None
    if student_username:
        redirect_url = url_for("core.educator_student_detail", username=student_username)
    else:
        # Fallback to dashboard if username not found
        redirect_url = url_for("core.educator_dashboard")
    
    response_data = {
        "results": results,
        "success": True,
        "message": f"Successfully uploaded {len(successful)} file(s). Processing in background.",
        "redirect_url": redirect_url
    }
    return jsonify(response_data), status_code


@bp.get("/api/job-status/<int:upload_id>")
@role_required("educator")
def api_job_status(upload_id: int):
    # CRITICAL: Reset database connection to ensure we're using PostgreSQL
    from models import reset_engine
    reset_engine()
    
    status = get_upload_status(upload_id)
    if status is None:
        return jsonify({"error": "Upload not found."}), 404
    return jsonify({"upload_id": upload_id, "status": status})


@bp.delete("/api/educator/students/<int:student_id>/uploads/<int:upload_id>")
@role_required("educator")
def api_delete_upload(student_id: int, upload_id: int):
    """Delete an upload for a student. Verifies the student belongs to the educator."""
    # CRITICAL: Reset database connection to ensure we're using PostgreSQL
    from models import reset_engine
    reset_engine()
    
    # Verify student belongs to educator
    overview = get_student_overview(current_user.id, student_id)
    if overview is None:
        return jsonify({"error": "Student not found or access denied."}), 404
    
    # Verify upload exists and belongs to this student
    upload = get_upload_by_id(upload_id)
    if not upload:
        return jsonify({"error": "Upload not found."}), 404
    
    upload_student_id = int(upload.get("student_id", 0))
    if upload_student_id != student_id:
        return jsonify({"error": "Upload does not belong to this student."}), 403
    
    # Delete the upload (this also deletes associated recommendations)
    try:
        delete_upload(upload_id)
        return jsonify({"success": True, "message": "Upload deleted successfully."}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to delete upload: {str(e)}"}), 500


@bp.delete("/api/educator/students/<int:student_id>")
@role_required("educator")
def api_delete_student(student_id: int):
    """Delete a student and all their associated data. Verifies the student belongs to the educator."""
    # Verify student belongs to educator
    overview = get_student_overview(current_user.id, student_id)
    if overview is None:
        return jsonify({"error": "Student not found or access denied."}), 404
    
    # Delete the student user (CASCADE will delete:
    # - student_profiles
    # - uploads (via student_id foreign key)
    # - recommendations (via upload_id foreign key in delete_upload)
    # - student_progress
    # - badges
    # - word_mastery
    # - quiz_attempts
    try:
        from models import delete_user
        delete_user(student_id)
        return jsonify({"success": True, "message": "Student and all associated data deleted successfully."}), 200
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to delete student {student_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to delete student: {str(e)}"}), 500


@bp.get("/quiz")
@role_required("student")
def student_quiz_page():
    return render_template("quiz.html")


@bp.get("/api/quiz/generate")
@role_required("student")
def api_quiz_generate():
    count_raw = request.args.get("count")
    try:
        target_count = _parse_optional_int(count_raw, "count", min_value=1, max_value=20)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if target_count is None:
        target_count = 10

    try:
        questions = build_quiz_questions(current_user.id, target_count=target_count)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"questions": questions, "total": len(questions)})


@bp.post("/api/quiz/submit")
@role_required("student")
def api_quiz_submit():
    payload = request.get_json(silent=True) or {}
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return jsonify({"error": "answers must be a list."}), 400
    if not answers:
        return jsonify({"error": "answers cannot be empty."}), 400

    try:
        result = score_quiz_and_update(current_user.id, answers)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result)

