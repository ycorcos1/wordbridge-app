from __future__ import annotations

import datetime
from typing import Optional

from models import (
    ensure_baseline_words_loaded,
    get_baseline_words_for_grade,
    get_student_profile,
    touch_student_profile_analysis,
    update_student_vocabulary_level,
)


def fetch_profile(student_id: int) -> Optional[dict[str, object]]:
    """Return the student profile row if it exists."""
    return get_student_profile(student_id)


def mark_analyzed(student_id: int, analyzed_at: Optional[datetime.datetime] = None) -> None:
    """Update the student's last analyzed timestamp."""
    touch_student_profile_analysis(student_id, analyzed_at)


def load_baseline_words(grade_level: int, limit: int = 200) -> list[dict[str, object]]:
    """Ensure baseline words are loaded and return subset for grade level."""
    ensure_baseline_words_loaded()
    return get_baseline_words_for_grade(grade_level, limit=limit)


def update_vocabulary_level(student_id: int, new_level: int) -> None:
    """Update the stored vocabulary level for a student."""
    update_student_vocabulary_level(student_id, new_level)

