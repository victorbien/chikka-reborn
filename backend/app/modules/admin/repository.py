"""Read-only aggregates and lookups for the administration dashboard, plus account restriction.

Every statement is parameterised; filter fragments are fixed strings chosen in code. Message
bodies and AI prompt/output text are never selected.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _rows(self, statement: str, params: dict[str, Any] | None = None) -> list[Any]:
        result = await self._session.execute(text(statement), params or {})
        return [dict(r) for r in result.mappings()]

    async def _one(self, statement: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        result = await self._session.execute(text(statement), params or {})
        return dict(result.mappings().one())

    # -- dashboard -------------------------------------------------------------------------

    async def user_stats(self) -> dict[str, Any]:
        return await self._one(
            """
            select
              count(*) filter (where deleted_at is null) as total_registered,
              count(*) filter (where status = 'active') as active_accounts,
              count(*) filter (where status = 'pending_verification') as pending_verification,
              count(*) filter (where status = 'suspended') as suspended,
              count(*) filter (where role = 'admin' and status = 'active') as administrators,
              count(*) filter (where status = 'active'
                  and last_seen_at > now() - interval '24 hours') as active_last_24h,
              count(*) filter (where status = 'active'
                  and last_seen_at > now() - interval '7 days') as active_last_7d,
              count(*) filter (where status = 'active'
                  and last_seen_at > now() - interval '30 days') as active_last_30d
            from public.profiles
            """
        )

    async def conversation_stats(self) -> dict[str, Any]:
        return await self._one(
            """
            select count(*) as total,
                   count(*) filter (where conversation_type = 'chikka') as chikka,
                   count(*) filter (where conversation_type = 'sms') as sms
            from public.conversations
            """
        )

    async def chikka_messages_sent(self) -> int:
        result = await self._session.execute(
            text("select count(*) from public.messages where channel = 'chikka'")
        )
        return int(result.scalar_one())

    async def sms_counts(self) -> list[dict[str, Any]]:
        return await self._rows(
            """
            select direction, status, is_simulated, count(*) as total
            from public.messages
            where channel = 'sms' and suppressed_at is null
            group by direction, status, is_simulated
            """
        )

    async def ai_totals(self) -> dict[str, Any]:
        return await self._one(
            """
            select count(*) as total_requests,
                   count(*) filter (where created_at > now() - interval '24 hours') as last_24h,
                   count(*) filter (where outcome <> 'success') as failed_requests,
                   coalesce(sum(input_tokens), 0) as input_tokens,
                   coalesce(sum(output_tokens), 0) as output_tokens
            from public.ai_assistance_logs
            """
        )

    async def credit_activity(self) -> list[dict[str, Any]]:
        return await self._rows(
            """
            select ledger_type,
                   count(*) as transactions,
                   coalesce(sum(balance_delta) filter (where entry_type in ('grant', 'top_up')), 0)
                       as units_granted,
                   coalesce(-sum(balance_delta) filter (where entry_type = 'deduction'), 0)
                       as units_deducted,
                   coalesce(sum(balance_delta) filter (where entry_type = 'refund'), 0)
                       as units_refunded,
                   coalesce(sum(balance_delta) filter (where entry_type = 'adjustment'), 0)
                       as units_adjusted
            from public.credit_transactions
            group by ledger_type
            """
        )

    # -- users -----------------------------------------------------------------------------

    _USER_COLUMNS = """
        p.id, p.username, p.display_name, u.email, p.role, p.status, p.country_code,
        p.created_at, p.last_seen_at, p.suspended_at
    """

    async def users(
        self,
        *,
        search: str | None,
        status: str | None,
        role: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["true"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            where.append(
                "(p.username ilike :q escape '\\' or p.display_name ilike :q escape '\\' "
                "or u.email ilike :q escape '\\')"
            )
            params["q"] = _like_pattern(search)
        if status:
            where.append("p.status = :status")
            params["status"] = status
        if role:
            where.append("p.role = :role")
            params["role"] = role
        clause = " and ".join(where)
        source = "from public.profiles p left join auth.users u on u.id = p.id"
        total = (
            await self._session.execute(
                text(f"select count(*) {source} where {clause}"),
                params,
            )
        ).scalar_one()
        rows = await self._rows(
            f"select {self._USER_COLUMNS} {source} where {clause} "
            "order by p.created_at desc, p.id limit :limit offset :offset",
            params,
        )
        return rows, int(total)

    async def user(self, user_id: UUID) -> dict[str, Any] | None:
        rows = await self._rows(
            f"select {self._USER_COLUMNS}, p.ai_enabled, p.deletion_requested_at "  # noqa: S608
            "from public.profiles p left join auth.users u on u.id = p.id where p.id = :id",
            {"id": user_id},
        )
        return rows[0] if rows else None

    async def verified_phone(self, user_id: UUID) -> str | None:
        result = await self._session.execute(
            text(
                "select e164 from public.phone_numbers "
                "where user_id = :id and status = 'verified' limit 1"
            ),
            {"id": user_id},
        )
        row = result.first()
        return str(row[0]) if row else None

    async def user_activity(self, user_id: UUID) -> dict[str, Any]:
        return await self._one(
            """
            select
              (select count(*) from public.messages
                 where sender_user_id = :id and channel = 'chikka') as chikka_messages_sent,
              (select count(*) from public.messages
                 where sender_user_id = :id and channel = 'sms'
                   and direction = 'outbound') as sms_sent,
              (select count(*) from public.message_deliveries
                 where recipient_user_id = :id and channel = 'sms') as sms_received,
              (select count(*) from public.conversation_members
                 where user_id = :id) as conversations,
              (select count(*) from public.ai_assistance_logs
                 where user_id = :id) as ai_requests,
              (select count(*) from public.abuse_reports
                 where reported_user_id = :id
                   and status in ('open', 'reviewing')) as open_reports_against,
              (select count(*) from auth.sessions
                 where user_id = :id
                   and (not_after is null or not_after > now())) as active_sessions
            """,
            {"id": user_id},
        )

    async def credit_balances(self, user_id: UUID) -> list[dict[str, Any]]:
        return await self._rows(
            "select ledger_type, balance_units, reserved_units "
            "from public.messaging_credits where user_id = :id order by ledger_type",
            {"id": user_id},
        )

    async def lock_profile(self, user_id: UUID) -> dict[str, Any] | None:
        rows = await self._rows(
            "select id, role, status from public.profiles where id = :id for update",
            {"id": user_id},
        )
        return rows[0] if rows else None

    async def suspend(self, user_id: UUID) -> None:
        await self._session.execute(
            text(
                "update public.profiles set status = 'suspended', suspended_at = now() "
                "where id = :id"
            ),
            {"id": user_id},
        )

    async def reinstate(self, user_id: UUID) -> None:
        await self._session.execute(
            text(
                "update public.profiles set status = 'active', suspended_at = null where id = :id"
            ),
            {"id": user_id},
        )

    async def revoke_sessions(self, user_id: UUID) -> int:
        result = await self._session.execute(
            text("delete from auth.sessions where user_id = :id"), {"id": user_id}
        )
        return int(getattr(result, "rowcount", 0) or 0)

    # -- SMS monitoring --------------------------------------------------------------------

    _SMS_JOIN = """
        from public.messages m
        left join lateral (
            select x.provider_message_id, x.failure_class, x.failure_code, x.recipient_phone,
                   x.recipient_user_id, x.attempt_number
            from public.message_deliveries x
            where x.message_id = m.id
            order by x.attempt_number desc limit 1
        ) d on true
    """
    _SMS_FROM = _SMS_JOIN + " where m.channel = 'sms' and m.suppressed_at is null"

    async def sms_messages(
        self,
        *,
        direction: str,
        status: str | None,
        is_simulated: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        where = " and m.direction = :direction"
        params: dict[str, Any] = {"direction": direction, "limit": limit, "offset": offset}
        if status:
            where += " and m.status = :status"
            params["status"] = status
        if is_simulated is not None:
            where += " and m.is_simulated = :simulated"
            params["simulated"] = is_simulated
        total = (
            await self._session.execute(
                text(f"select count(*) {self._SMS_FROM} {where}"),
                params,
            )
        ).scalar_one()
        rows = await self._rows(
            f"select {self._SMS_COLUMNS} {self._SMS_FROM} {where} "
            "order by m.created_at desc, m.id limit :limit offset :offset",
            params,
        )
        return rows, int(total)

    _SMS_COLUMNS = """
        m.id, m.direction, m.status, m.is_simulated, m.created_at, m.segment_count,
        m.sender_user_id, m.sender_phone, d.provider_message_id, d.failure_class, d.failure_code,
        d.recipient_phone, d.recipient_user_id, coalesce(d.attempt_number, 0) as attempts
    """

    async def sms_message(self, message_id: UUID) -> dict[str, Any] | None:
        rows = await self._rows(
            f"select {self._SMS_COLUMNS} {self._SMS_JOIN} where m.id = :id and m.channel = 'sms'",
            {"id": message_id},
        )
        return rows[0] if rows else None

    async def deliveries(self, message_id: UUID) -> list[dict[str, Any]]:
        return await self._rows(
            """
            select id, attempt_number, status, provider_message_id, is_simulated, failure_class,
                   failure_code, is_permanent, started_at, next_attempt_at, terminal_at
            from public.message_deliveries
            where message_id = :id order by attempt_number
            """,
            {"id": message_id},
        )

    async def delivery_events(self, delivery_ids: list[UUID]) -> list[dict[str, Any]]:
        if not delivery_ids:
            return []
        ids = [str(i) for i in delivery_ids]
        return await self._rows(
            """
            select delivery_id, source, provider_status, normalised_status, applied,
                   ignore_reason, received_at
            from public.message_delivery_events
            where delivery_id = any(cast(cast(:ids as text[]) as uuid[]))
            order by received_at, id
            """,
            {"ids": ids},
        )

    # -- AI monitoring ---------------------------------------------------------------------

    async def ai_features(self, since: datetime) -> list[dict[str, Any]]:
        return await self._rows(
            """
            select feature,
                   count(*) as requests,
                   count(*) filter (where outcome <> 'success') as failures,
                   count(*) filter (where user_decision in ('accepted', 'edited')) as accepted,
                   cast(avg(latency_ms) as int) as average_latency_ms,
                   coalesce(sum(input_tokens), 0) as input_tokens,
                   coalesce(sum(output_tokens), 0) as output_tokens
            from public.ai_assistance_logs
            where created_at >= :since
            group by feature order by requests desc, feature
            """,
            {"since": since},
        )

    async def ai_errors(self, since: datetime) -> list[dict[str, Any]]:
        return await self._rows(
            """
            select outcome, error_code, count(*) as count
            from public.ai_assistance_logs
            where created_at >= :since and outcome <> 'success'
            group by outcome, error_code order by count desc, outcome
            """,
            {"since": since},
        )

    async def ai_daily(self, since: datetime) -> list[dict[str, Any]]:
        return await self._rows(
            """
            select to_char(date_trunc('day', created_at), 'YYYY-MM-DD') as day,
                   count(*) as requests
            from public.ai_assistance_logs
            where created_at >= :since
            group by 1 order by 1
            """,
            {"since": since},
        )

    # -- provider overview -----------------------------------------------------------------

    async def active_provider(self) -> str | None:
        result = await self._session.execute(
            text("select provider from public.provider_configurations where is_active limit 1")
        )
        row = result.first()
        return str(row[0]) if row else None

    async def outbound_paused(self) -> bool:
        result = await self._session.execute(
            text("select value from public.system_settings where key = 'sms_outbound_paused'")
        )
        row = result.first()
        return bool(row and row[0] is True)

    # -- audit log -------------------------------------------------------------------------

    async def audit_logs(
        self,
        *,
        category: str | None,
        action: str | None,
        outcome: str | None,
        actor_id: UUID | None,
        since: datetime | None,
        until: datetime | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["true"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        for column, value in (
            ("category", category),
            ("outcome", outcome),
            ("actor_id", actor_id),
        ):
            if value is not None:
                where.append(f"{column} = :{column}")
                params[column] = value
        if action:
            where.append("action like :action escape '\\'")
            params["action"] = _like_pattern(action)
        if since:
            where.append("created_at >= :since")
            params["since"] = since
        if until:
            where.append("created_at < :until")
            params["until"] = until
        clause = " and ".join(where)
        total = (
            await self._session.execute(
                text(f"select count(*) from public.audit_logs where {clause}"),  # noqa: S608
                params,
            )
        ).scalar_one()
        rows = await self._rows(
            "select id, created_at, category, action, outcome, actor_id, actor_role, "  # noqa: S608
            "target_type, target_id, request_id "
            f"from public.audit_logs where {clause} "
            "order by created_at desc, id limit :limit offset :offset",
            params,
        )
        return rows, int(total)
