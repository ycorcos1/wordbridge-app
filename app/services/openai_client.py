from __future__ import annotations

from typing import List

from openai import OpenAI

from config.settings import get_settings

_CLIENT: OpenAI | None = None


class OpenAIConfigurationError(RuntimeError):
    """Raised when OpenAI client cannot be configured."""


class OpenAIResponseError(RuntimeError):
    """Raised when OpenAI returns an invalid or empty response."""


def _get_client() -> OpenAI:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise OpenAIConfigurationError("OPENAI_API_KEY is not configured.")

    _CLIENT = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _CLIENT


def generate_json_response(
    messages: List[dict[str, str]],
    *,
    model: str = "gpt-4o-mini",
    temperature: float = 0.4,
) -> str:
    """
    Call OpenAI to produce a JSON object response.

    Args:
        messages: Chat messages (system/user) describing the task.
        model: OpenAI model name to use.
        temperature: Sampling temperature (lower for deterministic output).
    """
    client = _get_client()
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=messages,
        )
    except Exception as exc:  # pragma: no cover - network errors
        raise OpenAIResponseError("OpenAI request failed.") from exc

    if not completion.choices:
        raise OpenAIResponseError("OpenAI response contained no choices.")

    choice = completion.choices[0]
    message = choice.message
    if not message or not message.content:
        raise OpenAIResponseError("OpenAI response message was empty.")

    return message.content

