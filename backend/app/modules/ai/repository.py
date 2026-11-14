"""Database access for the AI assistant. The service owns the transaction.

Raw SQL with bound parameters only. Two narrow reads/writes touch tables owned by other modules
(`profiles.ai_enabled`, `system_settings`) until those modules expose interfaces for them.
Only metadata is stored in ai_assistance_logs: never prompts, drafts or conversation text.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_HOURLY_LIMIT = 30


@dataclass(frozen=True)
class Gate:
    platform_enabled: bool
    user_enabled: bool
    hourly_limit: int


@dataclass(frozen=True)
class LogEntry:
    user_id: UUID
    conversation_id: UUID | None
    feature: str
    model_id: str
    prompt_version: str
    language: str | None
    outcome: str
    meaning_preserved: bool | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    error_code: str | None
    output_hash: str | None


class AiRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def gate(self, user_id: UUID) -> Gate:
        row = (
            await self._session.execute(
                text(
                    """
                    select
                      coalesce((select ai_enabled from public.profiles where id = :user_id),
                               false) as user_enabled,
                      coalesce((select (value #>> '{}') = 'true' from public.system_settings
                                where key = 'ai_enabled'), true) as platform_enabled,
                      coalesce((select case when jsonb_typeof(value) = 'number'
                                       then (value #>> '{}')::int end
                                from public.system_settings
                                where key = 'ai_user_limit_per_hour'), :default_limit)
                        as hourly_limit
                    """
                ),
                {"user_id": user_id, "default_limit": DEFAULT_HOURLY_LIMIT},
            )
        ).one()
        return Gate(
            platform_enabled=bool(row.platform_enabled),
            user_enabled=bool(row.user_enabled),
            hourly_limit=int(row.hourly_limit),
        )

    async def set_user_enabled(self, user_id: UUID, enabled: bool) -> None:
        await self._session.execute(
            text("update public.profiles set ai_enabled = :enabled where id = :user_id"),
            {"enabled": enabled, "user_id": user_id},
        )

    async def insert_log(self, entry: LogEntry) -> UUID:
        result = await self._session.execute(
            text(
                """
                insert into public.ai_assistance_logs
                  (user_id, conversation_id, feature, model_id, prompt_version, language,
                   outcome, meaning_preserved, input_tokens, output_tokens, latency_ms,
                   error_code, output_hash)
                values
                  (:user_id, :conversation_id, :feature, :model_id, :prompt_version, :language,
                   :outcome, :meaning_preserved, :input_tokens, :output_tokens, :latency_ms,
                   :error_code, :output_hash)
                returning id
                """
            ),
            {
                "user_id": entry.user_id,
                "conversation_id": entry.conversation_id,
                "feature": entry.feature,
                "model_id": entry.model_id,
                "prompt_version": entry.prompt_version,
                "language": entry.language,
                "outcome": entry.outcome,
                "meaning_preserved": entry.meaning_preserved,
                "input_tokens": entry.input_tokens,
                "output_tokens": entry.output_tokens,
                "latency_ms": entry.latency_ms,
                "error_code": entry.error_code,
                "output_hash": entry.output_hash,
            },
        )
        return UUID(str(result.scalar_one()))

    async def set_decision(self, log_id: UUID, user_id: UUID, decision: str) -> bool:
        """Record what the user did with a draft. Only the owner's own row can change."""
        result = await self._session.execute(
            text(
                "update public.ai_assistance_logs set user_decision = :decision "
                "where id = :log_id and user_id = :user_id"
            ),
            {"decision": decision, "log_id": log_id, "user_id": user_id},
        )
        return bool(getattr(result, "rowcount", 0))
