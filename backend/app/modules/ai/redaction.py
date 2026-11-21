"""Privacy boundary for conversation context sent to the AI provider.

Only the minimum is sent (docs: ai-guidelines): recent messages, labelled "me"/"them" instead of
names, with emails and phone-like numbers masked. The user's own draft is sent as written,
because masking it would change what gets translated or rewritten.
"""

import re

from app.modules.ai.settings import (
    MAX_CONTEXT_CHARS,
    MAX_CONTEXT_LINE_CHARS,
)
from app.modules.chat.context import ContextLine

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Eight or more digits with common separators: phone numbers, card and account numbers.
_LONG_NUMBER = re.compile(r"(?<![\w])\+?\d[\d\s().-]{6,}\d(?![\w])")


def redact(text: str) -> str:
    return _LONG_NUMBER.sub("[number]", _EMAIL.sub("[email]", text))


def minimise_context(lines: list[ContextLine], limit: int) -> list[dict[str, str]]:
    """Newest `limit` lines within a total character budget, redacted and labelled."""
    selected: list[dict[str, str]] = []
    budget = MAX_CONTEXT_CHARS
    for line in reversed(lines[-limit:]):
        text = redact(" ".join(line.text.split()))[:MAX_CONTEXT_LINE_CHARS]
        if not text:
            continue
        if len(text) > budget:
            break
        budget -= len(text)
        selected.append({"from": "me" if line.from_me else "them", "text": text})
    selected.reverse()
    return selected


def minimise_texts(texts: list[str]) -> list[str]:
    """Same treatment for free-form context strings supplied by the client."""
    cleaned = [redact(" ".join(text.split()))[:MAX_CONTEXT_LINE_CHARS] for text in texts]
    return [text for text in cleaned if text]
