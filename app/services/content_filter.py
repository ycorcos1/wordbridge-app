from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from better_profanity import profanity

from config.settings import get_settings

_PROFANITY_INITIALIZED = False
_EXTRA_WORDS_LOADED = False
_ALPHA_RE = re.compile(r"[A-Za-z]")


def _ensure_profanity_loaded() -> None:
    global _PROFANITY_INITIALIZED
    if not _PROFANITY_INITIALIZED:
        profanity.load_censor_words()
        _load_extra_words()
        _PROFANITY_INITIALIZED = True


def _load_extra_words() -> None:
    global _EXTRA_WORDS_LOADED
    if _EXTRA_WORDS_LOADED:
        return
    settings = get_settings()
    path_value = settings.CONTENT_FILTER_EXTRA_WORDS_PATH
    if not path_value:
        _EXTRA_WORDS_LOADED = True
        return
    try:
        path = Path(path_value)
    except (TypeError, ValueError):
        _EXTRA_WORDS_LOADED = True
        return
    if not path.exists() or not path.is_file():
        _EXTRA_WORDS_LOADED = True
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        _EXTRA_WORDS_LOADED = True
        return
    extra_words = [line.strip() for line in raw.splitlines() if line.strip()]
    if extra_words:
        profanity.add_censor_words(extra_words)
    _EXTRA_WORDS_LOADED = True


def _has_content(text: str) -> bool:
    return bool(text and _ALPHA_RE.search(text))


def _contains_blocked_language(*fields: str) -> bool:
    _ensure_profanity_loaded()
    for field in fields:
        if field and profanity.contains_profanity(field):
            return True
    return False


def normalize_recommendation(record: dict[str, object]) -> dict[str, object]:
    """Return a sanitized recommendation entry."""
    normalized = {
        "word": str(record.get("word", "")).strip(),
        "definition": str(record.get("definition", "")).strip(),
        "rationale": str(record.get("rationale", "")).strip(),
        "example_sentence": str(record.get("example_sentence", "")).strip(),
        "status": record.get("status", "pending"),
        "pinned": bool(record.get("pinned", False)),
    }
    difficulty_raw = record.get("difficulty_score", 1)
    try:
        difficulty_int = int(difficulty_raw)
    except (TypeError, ValueError):
        difficulty_int = 1
    normalized["difficulty_score"] = max(1, min(difficulty_int, 10))
    return normalized


def filter_recommendations(records: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Strip recommendations that fail profanity or basic validation checks."""
    settings = get_settings()
    normalized: list[dict[str, object]] = []

    for record in records:
        entry = normalize_recommendation(record)

        if not _has_content(entry["word"]) or not _has_content(entry["definition"]):
            continue

        if settings.CONTENT_FILTER_ENABLED and _contains_blocked_language(
            entry["word"], entry["definition"], entry["example_sentence"]
        ):
            continue

        normalized.append(entry)

    return normalized

