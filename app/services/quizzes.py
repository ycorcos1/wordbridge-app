from __future__ import annotations

import datetime
import random
from typing import Sequence

from models import (
    award_badges_if_needed,
    count_mastered_words,
    get_student_recommendations_by_ids,
    list_quiz_candidates,
    record_quiz_attempts,
    update_student_progress_for_quiz,
    update_word_mastery_from_results,
)

MAX_QUIZ_QUESTIONS = 10
MIN_APPROVED_WORDS = 5
DISTRACTOR_COUNT = 3


def _normalize_definition(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def build_quiz_questions(
    student_id: int,
    target_count: int = MAX_QUIZ_QUESTIONS,
) -> list[dict[str, object]]:
    """Return quiz questions for the student."""
    candidates = list_quiz_candidates(student_id, limit=200)
    filtered = [entry for entry in candidates if _normalize_definition(entry.get("definition"))]

    if len(filtered) < MIN_APPROVED_WORDS:
        raise ValueError("Not enough approved words to generate a quiz.")

    target = max(1, min(target_count, len(filtered)))
    recent_target = max(1, round(target * 0.7))
    if recent_target > target:
        recent_target = target

    recent_choices = filtered[:recent_target]
    remaining_pool = [entry for entry in filtered if entry not in recent_choices]
    older_needed = target - len(recent_choices)

    if older_needed > 0:
        if len(remaining_pool) >= older_needed:
            older_choices = random.sample(remaining_pool, older_needed)
        else:
            older_choices = remaining_pool
    else:
        older_choices = []

    selected = recent_choices + older_choices

    if len(selected) < target:
        for entry in filtered:
            if entry not in selected:
                selected.append(entry)
            if len(selected) >= target:
                break

    random.shuffle(selected)

    all_definitions = [_normalize_definition(entry.get("definition")) for entry in filtered]

    questions: list[dict[str, object]] = []
    for entry in selected:
        correct_definition = _normalize_definition(entry.get("definition"))
        other_definitions = [definition for definition in all_definitions if definition and definition != correct_definition]

        if len(other_definitions) >= DISTRACTOR_COUNT:
            distractors = random.sample(other_definitions, DISTRACTOR_COUNT)
        else:
            distractors = other_definitions[:]

        choices = [correct_definition] + distractors
        random.shuffle(choices)

        questions.append(
            {
                "word_id": entry["id"],
                "word": entry.get("word"),
                "definition_choices": choices,
                "correct_definition": correct_definition,
            }
        )

    return questions


def score_quiz_and_update(
    student_id: int,
    answers: Sequence[dict[str, object]],
    attempted_at: datetime.datetime | None = None,
) -> dict[str, object]:
    """Grade quiz answers and update persistent progress."""
    if not answers:
        raise ValueError("No answers provided.")

    timestamp = attempted_at or datetime.datetime.utcnow()
    word_ids: list[int] = []
    normalized_answers: list[tuple[int, str]] = []

    for entry in answers:
        word_id_raw = entry.get("word_id")
        if word_id_raw is None:
            continue
        try:
            word_id = int(word_id_raw)
        except (TypeError, ValueError):
            continue
        answer_text = _normalize_definition(entry.get("answer"))
        if not answer_text:
            continue
        word_ids.append(word_id)
        normalized_answers.append((word_id, answer_text))

    if not normalized_answers:
        raise ValueError("No valid answers to evaluate.")

    word_details = get_student_recommendations_by_ids(student_id, word_ids)
    if not word_details:
        raise ValueError("No matching vocabulary words found for scoring.")

    attempts_payload: list[dict[str, object]] = []
    mastery_payload: list[dict[str, object]] = []
    evaluated = 0
    correct_count = 0

    for word_id, answer_text in normalized_answers:
        details = word_details.get(word_id)
        if not details:
            continue
        evaluated += 1
        correct_definition = _normalize_definition(details.get("definition"))
        is_correct = answer_text.lower() == correct_definition.lower()
        if is_correct:
            correct_count += 1

        attempts_payload.append({"word_id": word_id, "correct": is_correct})
        mastery_payload.append({"word_id": word_id, "increment": 1 if is_correct else 0})

    if evaluated == 0:
        raise ValueError("Unable to evaluate quiz answers.")

    record_quiz_attempts(
        student_id=student_id,
        attempts=attempts_payload,
        attempted_at=timestamp,
    )

    mastery_summary = update_word_mastery_from_results(
        student_id=student_id,
        results=mastery_payload,
        attempted_at=timestamp,
    )

    progress = update_student_progress_for_quiz(
        student_id=student_id,
        correct=correct_count,
        total=evaluated,
        attempted_at=timestamp,
    )

    mastered_total = count_mastered_words(student_id)
    new_badges = award_badges_if_needed(student_id, mastered_total)

    last_quiz_at = progress.get("last_quiz_at")
    if isinstance(last_quiz_at, datetime.datetime):
        last_quiz_value = last_quiz_at.isoformat()
    else:
        last_quiz_value = str(last_quiz_at) if last_quiz_at else None

    response = {
        "correct": correct_count,
        "total": evaluated,
        "xp_earned": progress.get("xp_delta", 0),
        "bonus_awarded": progress.get("bonus", 0),
        "progress": {
            "xp": progress.get("xp", 0),
            "level": progress.get("level", 0),
            "streak_count": progress.get("streak_count", 0),
            "last_quiz_at": last_quiz_value,
        },
        "mastered_gained": mastery_summary.get("mastered_gained", 0),
        "badges_awarded": new_badges,
    }

    return response
