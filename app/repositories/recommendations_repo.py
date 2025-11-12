from __future__ import annotations

from typing import Iterable, Optional

from models import (
    count_recommendations_for_educator_filtered,
    create_recommendations,
    delete_recommendations_for_upload,
    list_recommendations_for_educator_filtered,
    list_recommendations_for_upload,
    update_recommendation_pinned_scoped,
    update_recommendation_rationale_scoped,
    update_recommendations_status_scoped,
)


def replace_recommendations_for_upload(
    *,
    student_id: int,
    upload_id: int,
    records: Iterable[dict[str, object]],
) -> None:
    """Replace existing recommendations for an upload with the provided batch."""
    batch = list(records)
    delete_recommendations_for_upload(upload_id)
    if not batch:
        return
    create_recommendations(student_id=student_id, upload_id=upload_id, records=batch)


def get_recommendations_for_upload(upload_id: int) -> list[dict[str, object]]:
    """Return stored recommendations for the upload."""
    return list_recommendations_for_upload(upload_id)


def list_for_educator(
    *,
    educator_id: int,
    student_id: Optional[int] = None,
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    date_from: Optional[object] = None,
    date_to: Optional[object] = None,
    status: Optional[str] = "pending",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, object]:
    """Return recommendations (with total) for an educator using provided filters."""
    items = list_recommendations_for_educator_filtered(
        educator_id=educator_id,
        student_id=student_id,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        date_from=date_from,
        date_to=date_to,
        status=status,
        limit=limit,
        offset=offset,
    )
    total = count_recommendations_for_educator_filtered(
        educator_id=educator_id,
        student_id=student_id,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        date_from=date_from,
        date_to=date_to,
        status=status,
    )
    return {"items": items, "total": total}


def bulk_update_status(
    *,
    educator_id: int,
    ids: list[int],
    status: str,
) -> int:
    """Update status for a batch of recommendations scoped to an educator."""
    if not ids:
        return 0
    return update_recommendations_status_scoped(
        educator_id=educator_id,
        ids=ids,
        status=status,
    )


def update_rationale(
    *,
    educator_id: int,
    recommendation_id: int,
    rationale: str,
) -> bool:
    """Update rationale for a single recommendation."""
    return update_recommendation_rationale_scoped(
        educator_id=educator_id,
        recommendation_id=recommendation_id,
        rationale=rationale,
    )


def set_pinned(
    *,
    educator_id: int,
    recommendation_id: int,
    pinned: bool,
) -> bool:
    """Toggle pinned flag for a recommendation."""
    return update_recommendation_pinned_scoped(
        educator_id=educator_id,
        recommendation_id=recommendation_id,
        pinned=pinned,
    )

