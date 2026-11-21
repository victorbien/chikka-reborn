"""Validation of model output. The model is untrusted: nothing reaches the user unchecked.

Every parser raises InvalidOutputError for empty, malformed or out-of-bounds output. The caller
turns that into "no suggestion" and never shows a half-valid answer.
"""

import json
import re
from typing import Any

from app.core.sanitize import clean_text
from app.modules.ai.settings import MAX_SUGGESTION_CHARS, MAX_SUMMARY_CHARS, MAX_TEXT_CHARS

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

# Typographic characters that force the Unicode (70-character) SMS encoding for no benefit.
_GSM_FRIENDLY = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }
)


class InvalidOutputError(ValueError):
    """The model answered, but not with something we can safely show."""


def parse_object(raw: str) -> dict[str, Any]:
    text = _FENCE.sub("", raw.strip())
    if not text:
        raise InvalidOutputError("empty response")
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise InvalidOutputError("response is not JSON") from exc
    if not isinstance(data, dict):
        raise InvalidOutputError("response is not an object")
    return data


def _text(value: object, *, limit: int) -> str:
    if not isinstance(value, str):
        raise InvalidOutputError("expected text")
    cleaned = clean_text(value)
    if not cleaned:
        raise InvalidOutputError("empty text")
    if len(cleaned) > limit:
        raise InvalidOutputError("text too long")
    return cleaned


def parse_text(raw: str, *, limit: int = MAX_TEXT_CHARS) -> str:
    return _text(parse_object(raw).get("text"), limit=limit)


def parse_summary(raw: str, *, limit: int) -> str:
    return _text(parse_object(raw).get("text"), limit=min(limit, MAX_SUMMARY_CHARS))


def parse_composed(raw: str, *, max_characters: int | None) -> str:
    return _text(
        parse_object(raw).get("text"), limit=min(max_characters or MAX_TEXT_CHARS, MAX_TEXT_CHARS)
    )


def parse_suggestions(raw: str, *, count: int) -> list[str]:
    items = parse_object(raw).get("suggestions")
    if not isinstance(items, list):
        raise InvalidOutputError("expected a list")
    seen: set[str] = set()
    suggestions: list[str] = []
    for item in items:
        try:
            cleaned = _text(item, limit=MAX_SUGGESTION_CHARS)
        except InvalidOutputError:
            continue
        if cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            suggestions.append(cleaned)
    if not suggestions:
        raise InvalidOutputError("no usable suggestions")
    return suggestions[:count]


class SmsOptimisation:
    """`text` is None when the model says the meaning cannot be kept within the limit."""

    def __init__(self, text: str | None, meaning_preserved: bool) -> None:
        self.text = text
        self.meaning_preserved = meaning_preserved


def parse_sms_optimisation(raw: str) -> SmsOptimisation:
    data = parse_object(raw)
    preserved = data.get("meaning_preserved")
    if not isinstance(preserved, bool):
        raise InvalidOutputError("missing meaning flag")
    if not preserved:
        return SmsOptimisation(None, False)
    text = _text(data.get("text"), limit=MAX_TEXT_CHARS).translate(_GSM_FRIENDLY)
    return SmsOptimisation(text, True)
