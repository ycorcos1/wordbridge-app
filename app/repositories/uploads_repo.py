from __future__ import annotations

import datetime
from typing import Optional

from models import get_upload_by_id, update_upload_status


def fetch_upload(upload_id: int) -> Optional[dict[str, object]]:
    """Return upload metadata for the provided identifier."""
    return get_upload_by_id(upload_id)


def mark_processing(upload_id: int) -> None:
    """Set upload status to processing."""
    update_upload_status(upload_id, "processing")


def mark_completed(upload_id: int, *, processed_at: Optional[datetime.datetime] = None) -> None:
    """Set upload status to completed."""
    update_upload_status(upload_id, "completed", processed_at)


def mark_failed(upload_id: int, *, processed_at: Optional[datetime.datetime] = None) -> None:
    """Set upload status to failed."""
    update_upload_status(upload_id, "failed", processed_at)

