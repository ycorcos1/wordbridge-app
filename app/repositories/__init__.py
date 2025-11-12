"""Database repository helpers for WordBridge."""

from .uploads_repo import fetch_upload, mark_completed, mark_failed, mark_processing
from .recommendations_repo import (
    replace_recommendations_for_upload,
    get_recommendations_for_upload,
    list_for_educator,
    bulk_update_status,
    update_rationale,
    set_pinned,
)
from .student_profiles_repo import (
    fetch_profile,
    mark_analyzed,
    load_baseline_words,
    update_vocabulary_level,
)

__all__ = [
    "fetch_upload",
    "mark_completed",
    "mark_failed",
    "mark_processing",
    "replace_recommendations_for_upload",
    "get_recommendations_for_upload",
    "list_for_educator",
    "bulk_update_status",
    "update_rationale",
    "set_pinned",
    "fetch_profile",
    "mark_analyzed",
    "load_baseline_words",
    "update_vocabulary_level",
]

