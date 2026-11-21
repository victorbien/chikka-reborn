"""In-memory stand-ins so AI service tests need no database, network or real model."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.security import AuthenticatedUser
from app.integrations.ai.base import AiProviderError
from app.integrations.ai.mock import MockAiProvider
from app.modules.ai.repository import Gate, LogEntry
from app.modules.ai.service import AiService
from app.modules.chat.context import ContextLine, ConversationAiContext
from app.modules.rate_limits.service import Limit

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000002")
CONVERSATION_ID = UUID("00000000-0000-0000-0000-0000000000c1")


def make_user(user_id: UUID = USER_ID) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user_id,
        session_id=uuid4(),
        email="fake.user@example.com",
        role="user",
        status="active",
        onboarded=True,
    )


@dataclass
class AiState:
    """What the fake database holds."""

    platform_enabled: bool = True
    user_enabled: dict[UUID, bool] = field(default_factory=dict)
    hourly_limit: int = 30
    logs: dict[UUID, tuple[UUID, LogEntry]] = field(default_factory=dict)
    decisions: dict[UUID, str] = field(default_factory=dict)
    fail_log_writes: bool = False


class FakeAiRepository:
    def __init__(self, state: AiState) -> None:
        self._state = state

    async def gate(self, user_id: UUID) -> Gate:
        return Gate(
            platform_enabled=self._state.platform_enabled,
            user_enabled=self._state.user_enabled.get(user_id, False),
            hourly_limit=self._state.hourly_limit,
        )

    async def set_user_enabled(self, user_id: UUID, enabled: bool) -> None:
        self._state.user_enabled[user_id] = enabled

    async def insert_log(self, entry: LogEntry) -> UUID:
        if self._state.fail_log_writes:
            raise RuntimeError("database down")
        log_id = uuid4()
        self._state.logs[log_id] = (entry.user_id, entry)
        return log_id

    async def set_decision(self, log_id: UUID, user_id: UUID, decision: str) -> bool:
        owner = self._state.logs.get(log_id)
        if owner is None or owner[0] != user_id:
            return False
        self._state.decisions[log_id] = decision
        return True


class FakeDatabase:
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[object]:
        yield object()


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def record(self, session: object, **kwargs: Any) -> None:
        self.events.append(kwargs)


class FakeLimiter:
    def __init__(self) -> None:
        self.hits: list[tuple[Limit, str]] = []
        self.blocked = False

    async def hit(self, limit: Limit, subject: str) -> None:
        self.hits.append((limit, subject))
        if self.blocked:
            from app.core.exceptions import RateLimitedError

            raise RateLimitedError(60, limit.message)


class FakeChat:
    """Stands in for ChatService.ai_context. Only the conversation members may read it."""

    def __init__(self) -> None:
        self.lines: list[ContextLine] = []
        self.ai_enabled = True
        self.members: set[UUID] = {USER_ID}
        self.requested_limits: list[int] = []

    async def ai_context(
        self, user: AuthenticatedUser, conversation_id: UUID, limit: int
    ) -> ConversationAiContext:
        from app.core.exceptions import NotFoundError

        self.requested_limits.append(limit)
        if user.id not in self.members or conversation_id != CONVERSATION_ID:
            raise NotFoundError("Conversation not found.")
        return ConversationAiContext(
            ai_enabled=self.ai_enabled, lines=self.lines[-limit:] if self.ai_enabled else []
        )


@dataclass
class AiHarness:
    service: AiService
    provider: MockAiProvider
    state: AiState
    chat: FakeChat
    limiter: FakeLimiter
    audit: FakeAudit
    user: AuthenticatedUser


def build_harness(
    *, enabled: bool = True, script: list[str | AiProviderError] | None = None
) -> AiHarness:
    state = AiState()
    state.user_enabled[USER_ID] = enabled
    provider = MockAiProvider(script=script or [])
    chat = FakeChat()
    limiter = FakeLimiter()
    audit = FakeAudit()
    service = AiService(
        settings=Settings(_env_file=None, app_env="test"),  # type: ignore[call-arg]
        database=FakeDatabase(),  # type: ignore[arg-type]
        provider=provider,
        limiter=limiter,
        chat=chat,
        audit=audit,  # type: ignore[arg-type]
        repository_factory=lambda _session: FakeAiRepository(state),  # type: ignore[arg-type,return-value]
    )
    return AiHarness(service, provider, state, chat, limiter, audit, make_user())
