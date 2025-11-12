from __future__ import annotations

import re

EMAIL_REGEX = re.compile(
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,24}\b",
    re.IGNORECASE,
)
PHONE_REGEX = re.compile(
    r"""
    (?:(?:\+?1[\s\-\.]?)?(?:\(?\d{3}\)?[\s\-\.]?)\d{3}[\s\-\.]?\d{4})
    """,
    re.VERBOSE,
)
LABELED_NAME_REGEX = re.compile(
    r"\b(?:Name|Student|Teacher|Educator|Parent)\s*[:\-]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+"
)
FULL_NAME_REGEX = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"
)


def scrub_pii(text: str) -> str:
    """Replace common PII patterns with anonymized tokens."""
    if not text:
        return text
    cleaned = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
    cleaned = PHONE_REGEX.sub("[REDACTED_PHONE]", cleaned)
    cleaned = LABELED_NAME_REGEX.sub("[REDACTED_NAME]", cleaned)
    cleaned = FULL_NAME_REGEX.sub("[REDACTED_NAME]", cleaned)
    return cleaned


def contains_pii(text: str) -> bool:
    """Return True when text appears to contain email, phone, or labeled names."""
    if not text:
        return False
    return bool(
        EMAIL_REGEX.search(text)
        or PHONE_REGEX.search(text)
        or LABELED_NAME_REGEX.search(text)
        or FULL_NAME_REGEX.search(text)
    )

