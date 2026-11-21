"""Read-only view of a conversation for other modules (the AI assistant).

Exposed as data, so the AI module never touches chat tables. Nothing here marks messages as
delivered or read: fetching context for an assistant is not the user reading the chat.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextLine:
    from_me: bool
    text: str


@dataclass(frozen=True)
class ConversationAiContext:
    """`ai_enabled` is the member's per-conversation switch (FR-AI-005 AC4)."""

    ai_enabled: bool
    lines: list[ContextLine]
