from __future__ import annotations

from app.services import pii


def test_scrub_pii_replaces_email_phone_and_name():
    text = (
        "Student: Jane Doe\n"
        "Contact: jane.doe@example.com or (555) 123-4567 for more info.\n"
        "Alternate: +1 555.123.4567"
    )
    cleaned = pii.scrub_pii(text)
    assert "[REDACTED_EMAIL]" in cleaned
    assert "[REDACTED_PHONE]" in cleaned
    assert "[REDACTED_NAME]" in cleaned


def test_scrub_pii_handles_unlabeled_full_names():
    text = "John Smith wrote this passage. Mary Johnson edited it."
    cleaned = pii.scrub_pii(text)
    assert "John Smith" not in cleaned
    assert "Mary Johnson" not in cleaned
    assert cleaned.count("[REDACTED_NAME]") >= 2


def test_contains_pii_detects_common_patterns():
    assert pii.contains_pii("Email me at teacher@example.com")
    assert pii.contains_pii("Call 555-000-9999")
    assert pii.contains_pii("Student: John Smith")
    assert pii.contains_pii("This essay is by Jane Doe")
    assert not pii.contains_pii("There is nothing sensitive here.")

