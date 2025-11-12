from __future__ import annotations

from app.services import content_filter


def test_filter_recommendations_removes_profanity(monkeypatch):
    monkeypatch.setenv("CONTENT_FILTER_ENABLED", "true")
    safe = {
        "word": "analyze",
        "definition": "Examine something carefully to understand it better.",
        "rationale": "Helps with scientific writing.",
        "example_sentence": "We will analyze the data carefully.",
        "difficulty_score": 4,
    }
    unsafe = {
        "word": "curse",
        "definition": "A bad word like damn.",
        "rationale": "Inappropriate language.",
        "example_sentence": "This is a damn example.",
        "difficulty_score": 5,
    }

    filtered = content_filter.filter_recommendations([safe, unsafe])
    assert len(filtered) == 1
    assert filtered[0]["word"] == "analyze"


def test_filter_normalizes_difficulty_and_defaults(monkeypatch):
    monkeypatch.setenv("CONTENT_FILTER_ENABLED", "false")

    record = {
        "word": "Synthesize",
        "definition": "Combine parts to make a whole.",
        "rationale": "Supports essay writing.",
        "example_sentence": "Students synthesize information from multiple sources.",
        "difficulty_score": 15,
        "status": "pending",
        "pinned": True,
    }

    filtered = content_filter.filter_recommendations([record])
    assert filtered[0]["difficulty_score"] == 10  # capped at max 10
    assert filtered[0]["pinned"] is True


def test_filter_uses_extra_sensitive_wordlist(monkeypatch, tmp_path):
    extra_terms = tmp_path / "sensitive.txt"
    extra_terms.write_text("forbidden\n", encoding="utf-8")

    monkeypatch.setenv("CONTENT_FILTER_ENABLED", "true")
    monkeypatch.setenv("CONTENT_FILTER_EXTRA_WORDS_PATH", str(extra_terms))
    monkeypatch.setattr(content_filter, "_PROFANITY_INITIALIZED", False)
    monkeypatch.setattr(content_filter, "_EXTRA_WORDS_LOADED", False)

    record = {
        "word": "Vocabulary",
        "definition": "Definition containing a forbidden term.",
        "rationale": "Because this includes a forbidden example.",
        "example_sentence": "This sentence mentions a forbidden topic.",
        "difficulty_score": 5,
    }

    filtered = content_filter.filter_recommendations([record])
    assert filtered == []

