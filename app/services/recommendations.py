from __future__ import annotations

import json
from typing import Iterable

from config.settings import get_settings

from . import openai_client

RESPONSE_JSON_KEY = "recommendations"
MAX_SAMPLE_CHARS = 6000
BASELINE_SUMMARY_LIMIT = 25


class RecommendationParseError(RuntimeError):
    """Raised when the OpenAI response cannot be parsed into recommendation objects."""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _baseline_summary(baseline_words: Iterable[dict[str, object]]) -> str:
    unique_words: list[str] = []
    for entry in baseline_words:
        word = str(entry.get("word", "")).strip()
        if not word:
            continue
        if word.lower() not in {w.lower() for w in unique_words}:
            unique_words.append(word)
        if len(unique_words) >= BASELINE_SUMMARY_LIMIT:
            break
    return ", ".join(unique_words)


def build_messages(
    *,
    student_profile: dict[str, object],
    writing_sample: str,
    baseline_words: Iterable[dict[str, object]],
    target_batch_size: int = 5,
) -> list[dict[str, str]]:
    """Build chat messages for the OpenAI call."""
    grade_level = student_profile.get("grade_level", "unknown")
    vocabulary_level = student_profile.get("vocabulary_level", "unknown")
    baseline_list = _baseline_summary(baseline_words)

    system_prompt = (
        "You are an expert literacy coach who creates age-appropriate vocabulary suggestions "
        "for middle school students. Avoid profanity and overly mature language. "
        "Return JSON with a key 'recommendations' containing a list of objects. "
        "Each object must include the fields: "
        "'word' (string), 'definition' (string), 'rationale' (string explaining why "
        "the student should learn the word), 'difficulty_score' (integer 1-10), "
        "and 'example_sentence' (string, age-appropriate, using the word correctly). "
        "Do not include any additional keys or commentary."
    )

    writing_excerpt = _truncate(writing_sample, MAX_SAMPLE_CHARS)

    user_prompt_lines = [
        f"Student grade level: {grade_level}",
        f"Current vocabulary level estimate: {vocabulary_level}",
        f"Target recommendations: {max(5, target_batch_size)} words",
    ]
    if baseline_list:
        user_prompt_lines.append(
            "Baseline vocabulary already familiar to the student (avoid duplicates): "
            + baseline_list
        )
    user_prompt_lines.append("Student writing sample (cleaned):")
    user_prompt_lines.append(writing_excerpt)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_prompt_lines)},
    ]
    return messages


def parse_recommendations_from_json(payload_str: str) -> list[dict[str, object]]:
    """Parse OpenAI JSON response into a list of recommendation objects."""
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        raise RecommendationParseError("Failed to parse JSON from OpenAI response.") from exc

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get(RESPONSE_JSON_KEY)
    else:
        raise RecommendationParseError("Unexpected response format from OpenAI.")

    if not isinstance(items, list):
        raise RecommendationParseError("OpenAI did not return a list of recommendations.")

    normalized: list[dict[str, object]] = []
    seen_words: set[str] = set()

    for entry in items:
        if not isinstance(entry, dict):
            continue
        word = str(entry.get("word", "")).strip()
        if not word:
            continue
        word_lower = word.lower()
        if word_lower in seen_words:
            continue
        seen_words.add(word_lower)

        normalized.append(
            {
                "word": word,
                "definition": str(entry.get("definition", "")).strip(),
                "rationale": str(entry.get("rationale", "")).strip(),
                "difficulty_score": entry.get("difficulty_score", 1),
                "example_sentence": str(entry.get("example_sentence", "")).strip(),
            }
        )

    return normalized


def generate_recommendations(
    *,
    student_profile: dict[str, object],
    writing_sample: str,
    baseline_words: Iterable[dict[str, object]],
    target_batch_size: int = 5,
) -> list[dict[str, object]]:
    """Return AI-generated vocabulary recommendations for the provided writing sample."""
    settings = get_settings()
    messages = build_messages(
        student_profile=student_profile,
        writing_sample=writing_sample,
        baseline_words=baseline_words,
        target_batch_size=target_batch_size,
    )
    response_str = openai_client.generate_json_response(
        messages,
        model="gpt-4o-mini",
        temperature=0.4,
    )
    recommendations = parse_recommendations_from_json(response_str)

    if len(recommendations) < max(5, target_batch_size):
        raise RecommendationParseError(
            "OpenAI returned fewer recommendations than required."
        )

    return recommendations

