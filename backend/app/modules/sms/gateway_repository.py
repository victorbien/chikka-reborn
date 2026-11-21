"""Database access for the SMS engine: dispatch, status callbacks, webhooks and inbound."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Columns the engine may change on a delivery attempt. Names are never taken from input.
_UPDATABLE = frozenset(
    {
        "status",
        "provider_status",
        "provider_message_id",
        "failure_class",
        "is_permanent",
        "failure_code",
        "failure_reason",
        "http_status",
        "next_attempt_at",
        "locked_until",
        "started_at",
        "accepted_at",
        "sent_at",
        "delivered_at",
        "terminal_at",
        "provider_response",
    }
)

DELIVERY_FOR_UPDATE = """
    select d.id, d.message_id, d.attempt_number, d.status, d.failure_class, d.started_at,
           d.recipient_phone, d.provider_configuration_id, d.is_simulated, d.provider_message_id,
           d.accepted_at, d.sent_at, d.terminal_at, d.is_permanent,
           m.body, m.sender_user_id, m.idempotency_key, m.created_at as message_created_at,
           m.capability_id, m.conversation_id
    from public.message_deliveries d
    join public.messages m on m.id = d.message_id
"""


class GatewayRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- dispatch --------------------------------------------------------------------------

    async def claim_due(
        self, now: datetime, lease_until: datetime, limit: int
    ) -> list[dict[str, Any]]:
        """Lease due attempts. `previous_started_at` shows whether an earlier claim already
        began (and may have reached the provider) without recording an outcome."""
        result = await self._session.execute(
            text(
                """
                with due as (
                    select d.id, d.started_at as previous_started_at
                    from public.message_deliveries d
                    where d.channel = 'sms' and d.status = 'queued'
                      and d.next_attempt_at <= :now
                      and (d.locked_until is null or d.locked_until < :now)
                    order by d.next_attempt_at
                    limit :limit
                    for update of d skip locked
                )
                update public.message_deliveries d
                   set locked_until = :lease, started_at = coalesce(d.started_at, :now)
                  from due
                 where d.id = due.id
                returning d.id, due.previous_started_at, d.failure_class
                """
            ),
            {"now": now, "lease": lease_until, "limit": limit},
        )
        return [dict(r) for r in result.mappings()]

    async def delivery(self, delivery_id: UUID, *, lock: bool = True) -> dict[str, Any] | None:
        suffix = " for update of d" if lock else ""
        result = await self._session.execute(
            text(DELIVERY_FOR_UPDATE + " where d.id = :id" + suffix), {"id": delivery_id}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def delivery_by_provider_id(
        self, cfg_id: UUID, provider_message_id: str
    ) -> dict[str, Any] | None:
        result = await self._session.execute(
            text(
                DELIVERY_FOR_UPDATE
                + " where d.channel = 'sms' and d.provider_configuration_id = :cfg"
                " and d.provider_message_id = :pmid for update of d"
            ),
            {"cfg": cfg_id, "pmid": provider_message_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def delivery_by_correlation(
        self, cfg_id: UUID, delivery_id: UUID
    ) -> dict[str, Any] | None:
        result = await self._session.execute(
            text(
                DELIVERY_FOR_UPDATE
                + " where d.id = :id and d.channel = 'sms' and d.provider_configuration_id = :cfg"
                " for update of d"
            ),
            {"id": delivery_id, "cfg": cfg_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def update_delivery(self, delivery_id: UUID, values: dict[str, Any]) -> None:
        unknown = set(values) - _UPDATABLE
        if unknown:
            raise ValueError(f"not updatable: {sorted(unknown)}")
        assignments: list[str] = []
        params: dict[str, Any] = {"id": delivery_id}
        for column, value in values.items():
            if column == "provider_response":
                assignments.append("provider_response = cast(:provider_response as jsonb)")
                params[column] = None if value is None else json.dumps(value, default=str)
            else:
                assignments.append(f"{column} = :{column}")
                params[column] = value
        if not assignments:
            return
        await self._session.execute(
            text(f"update public.message_deliveries set {', '.join(assignments)} where id = :id"),  # noqa: S608
            params,
        )

    async def insert_retry_attempt(self, previous: dict[str, Any], due: datetime) -> UUID | None:
        result = await self._session.execute(
            text(
                """
                insert into public.message_deliveries
                    (message_id, attempt_number, retry_of_delivery_id, channel,
                     provider_configuration_id, recipient_phone, status, is_simulated,
                     next_attempt_at)
                values
                    (:m, :n, :prev, 'sms', :cfg, cast(:r as public.e164), 'queued', :sim, :due)
                on conflict (message_id, attempt_number) do nothing
                returning id
                """
            ),
            {
                "m": previous["message_id"],
                "n": previous["attempt_number"] + 1,
                "prev": previous["id"],
                "cfg": previous["provider_configuration_id"],
                "r": previous["recipient_phone"],
                "sim": previous["is_simulated"],
                "due": due,
            },
        )
        row = result.first()
        return UUID(str(row[0])) if row else None

    async def insert_event(
        self,
        *,
        delivery_id: UUID,
        webhook_id: UUID | None,
        dedupe_key: str,
        source: str,
        provider_status: str | None,
        normalised_status: str,
        error_code: str | None,
        occurred_at: datetime | None,
        applied: bool,
        ignore_reason: str | None,
    ) -> bool:
        """False when this event was already recorded (duplicate callback or poll)."""
        result = await self._session.execute(
            text(
                """
                insert into public.message_delivery_events
                    (delivery_id, webhook_id, dedupe_key, source, provider_status,
                     normalised_status, provider_error_code, occurred_at, applied, ignore_reason)
                values (:d, :w, :k, :src, :ps, :ns, :err, :occ, :applied, :reason)
                on conflict (delivery_id, dedupe_key) do nothing
                returning id
                """
            ),
            {
                "d": delivery_id,
                "w": webhook_id,
                "k": dedupe_key,
                "src": source,
                "ps": provider_status,
                "ns": normalised_status,
                "err": error_code,
                "occ": occurred_at,
                "applied": applied,
                "reason": ignore_reason,
            },
        )
        return result.first() is not None

    async def stale_for_poll(self, now: datetime, limit: int) -> list[dict[str, Any]]:
        result = await self._session.execute(
            text(
                """
                select id, provider_message_id, created_at, status
                from public.message_deliveries
                where channel = 'sms' and status in ('accepted', 'sent')
                  and provider_message_id is not null and next_attempt_at <= :now
                order by next_attempt_at limit :limit
                """
            ),
            {"now": now, "limit": limit},
        )
        return [dict(r) for r in result.mappings()]

    async def configuration_id(self, provider: str, mode: str) -> UUID | None:
        result = await self._session.execute(
            text("select id from public.provider_configurations where provider = :p and mode = :m"),
            {"p": provider, "m": mode},
        )
        row = result.first()
        return UUID(str(row[0])) if row else None

    async def sender_for(self, user_id: UUID, remote: str) -> str | None:
        result = await self._session.execute(
            text(
                "select platform_number from public.sms_routes where user_id = :u "
                "and remote_number = cast(:r as public.e164) and status = 'active'"
            ),
            {"u": user_id, "r": remote},
        )
        row = result.first()
        return str(row[0]) if row else None

    async def capability_provider_settings(self, capability_id: UUID | None) -> dict[str, Any]:
        if capability_id is None:
            return {}
        result = await self._session.execute(
            text("select provider_settings from public.sms_country_capabilities where id = :id"),
            {"id": capability_id},
        )
        row = result.first()
        return dict(row[0] or {}) if row else {}

    async def conversation_owner(self, conversation_id: UUID) -> UUID | None:
        result = await self._session.execute(
            text(
                "select user_id from public.conversation_members "
                "where conversation_id = :c and left_at is null limit 1"
            ),
            {"c": conversation_id},
        )
        row = result.first()
        return UUID(str(row[0])) if row else None

    # -- webhooks --------------------------------------------------------------------------

    async def insert_webhook(
        self,
        *,
        provider: str,
        cfg_id: UUID | None,
        kind: str,
        dedupe_key: str,
        provider_message_id: str | None,
        payload: dict[str, Any],
        is_simulated: bool,
        now: datetime,
    ) -> UUID | None:
        result = await self._session.execute(
            text(
                """
                insert into public.provider_webhooks
                    (provider, provider_configuration_id, kind, dedupe_key, provider_message_id,
                     raw_payload, signature_verified_at, is_simulated, received_at)
                values (:p, :cfg, :kind, :k, :pmid, cast(:payload as jsonb), :now, :sim, :now)
                on conflict (provider, kind, dedupe_key) do nothing
                returning id
                """
            ),
            {
                "p": provider,
                "cfg": cfg_id,
                "kind": kind,
                "k": dedupe_key,
                "pmid": provider_message_id,
                "payload": json.dumps(payload, default=str),
                "now": now,
                "sim": is_simulated,
            },
        )
        row = result.first()
        return UUID(str(row[0])) if row else None

    async def webhook(self, webhook_id: UUID) -> dict[str, Any] | None:
        result = await self._session.execute(
            text(
                "select id, provider, provider_configuration_id, kind, provider_message_id, "
                "raw_payload, is_simulated, processing_status, process_attempts, received_at "
                "from public.provider_webhooks where id = :id for update"
            ),
            {"id": webhook_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def finish_webhook(
        self,
        webhook_id: UUID,
        *,
        status: str,
        routing_result: str | None = None,
        error_code: str | None = None,
        delivery_id: UUID | None = None,
        message_id: UUID | None = None,
        next_process_at: datetime | None = None,
        attempts_increment: int = 0,
        now: datetime,
    ) -> None:
        await self._session.execute(
            text(
                """
                update public.provider_webhooks
                   set processing_status = :status, routing_result = :routing,
                       error_code = :error, delivery_id = :delivery, message_id = :message,
                       next_process_at = :next, process_attempts = process_attempts + :inc,
                       processed_at = case when :status = 'processed' then :now
                                         else processed_at end
                 where id = :id
                """
            ),
            {
                "id": webhook_id,
                "status": status,
                "routing": routing_result,
                "error": error_code,
                "delivery": delivery_id,
                "message": message_id,
                "next": next_process_at,
                "inc": attempts_increment,
                "now": now,
            },
        )

    async def pending_webhooks(self, now: datetime, limit: int) -> list[UUID]:
        result = await self._session.execute(
            text(
                """
                select id from public.provider_webhooks
                where processing_status in ('received', 'failed', 'orphaned')
                  and ((next_process_at is not null and next_process_at <= :now)
                       or (next_process_at is null and processing_status = 'received'
                           and received_at < :now - interval '30 seconds'))
                order by received_at limit :limit
                """
            ),
            {"now": now, "limit": limit},
        )
        return [UUID(str(r[0])) for r in result]

    # -- inbound ---------------------------------------------------------------------------

    async def route_owner(self, platform: str, remote: str) -> tuple[UUID, UUID] | None:
        result = await self._session.execute(
            text(
                "select user_id, conversation_id from public.sms_routes "
                "where platform_number = cast(:p as public.e164) "
                "and remote_number = cast(:r as public.e164) "
                "and status = 'active' and expires_at >= now()"
            ),
            {"p": platform, "r": remote},
        )
        row = result.first()
        return (UUID(str(row[0])), UUID(str(row[1]))) if row else None

    async def route_owners_by_remote(self, remote: str) -> list[UUID]:
        result = await self._session.execute(
            text(
                "select distinct user_id from public.sms_routes "
                "where remote_number = cast(:r as public.e164) and status = 'active'"
            ),
            {"r": remote},
        )
        return [UUID(str(r[0])) for r in result]

    async def user_is_active(self, user_id: UUID) -> bool:
        result = await self._session.execute(
            text(
                "select 1 from public.profiles where id = :u and status = 'active' "
                "and deleted_at is null"
            ),
            {"u": user_id},
        )
        return result.first() is not None

    async def conversation_muted(self, conversation_id: UUID, user_id: UUID) -> bool:
        result = await self._session.execute(
            text(
                "select (muted_indefinitely or coalesce(muted_until > now(), false)) "
                "from public.conversation_members where conversation_id = :c and user_id = :u"
            ),
            {"c": conversation_id, "u": user_id},
        )
        row = result.first()
        return bool(row[0]) if row else False

    async def insert_inbound_message(
        self,
        *,
        conversation_id: UUID,
        remote: str,
        body: str,
        truncated: bool,
        encoding: str,
        char_count: int,
        segment_count: int,
        is_simulated: bool,
        suppressed: bool,
    ) -> UUID:
        result = await self._session.execute(
            text(
                """
                insert into public.messages
                    (conversation_id, channel, direction, sender_phone, body, body_truncated,
                     encoding, char_count, segment_count, status, is_simulated,
                     suppressed_at, suppressed_reason)
                values
                    (:c, 'sms', 'inbound', cast(:r as public.e164), :body, :trunc, :enc, :chars,
                     :segs, 'received', :sim,
                     case when :suppressed then now() end,
                     case when :suppressed then 'blocked' end)
                returning id
                """
            ),
            {
                "c": conversation_id,
                "r": remote,
                "body": body,
                "trunc": truncated,
                "enc": encoding,
                "chars": char_count,
                "segs": segment_count,
                "sim": is_simulated,
                "suppressed": suppressed,
            },
        )
        return UUID(str(result.scalar_one()))

    async def insert_inbound_receipt(
        self,
        *,
        message_id: UUID,
        cfg_id: UUID,
        user_id: UUID,
        provider_message_id: str,
        is_simulated: bool,
        now: datetime,
    ) -> UUID | None:
        """The single delivery row of an inbound SMS. Its unique (provider, id) index is a second
        guard against processing one provider message twice."""
        result = await self._session.execute(
            text(
                """
                insert into public.message_deliveries
                    (message_id, channel, provider_configuration_id, recipient_user_id, status,
                     provider_message_id, is_simulated, delivered_at, accepted_at, sent_at)
                values (:m, 'sms', :cfg, :u, 'delivered', :pmid, :sim, :now, :now, :now)
                on conflict (provider_configuration_id, provider_message_id)
                    where provider_message_id is not null do nothing
                returning id
                """
            ),
            {
                "m": message_id,
                "cfg": cfg_id,
                "u": user_id,
                "pmid": provider_message_id,
                "sim": is_simulated,
                "now": now,
            },
        )
        row = result.first()
        return UUID(str(row[0])) if row else None

    async def unarchive_unmuted(self, conversation_id: UUID, user_id: UUID) -> None:
        await self._session.execute(
            text(
                "update public.conversation_members set is_archived = false "
                "where conversation_id = :c and user_id = :u and is_archived "
                "and not muted_indefinitely and coalesce(muted_until <= now(), true)"
            ),
            {"c": conversation_id, "u": user_id},
        )

    async def is_blocked_phone(self, user_id: UUID, phone: str) -> bool:
        result = await self._session.execute(
            text(
                "select 1 from public.user_blocks where blocker_id = :u "
                "and blocked_phone = cast(:p as public.e164)"
            ),
            {"u": user_id, "p": phone},
        )
        return result.first() is not None

    async def inbound_capability(self, region: str | None) -> str | None:
        if not region:
            return None
        result = await self._session.execute(
            text(
                "select inbound_support from public.sms_country_capabilities "
                "where country_code = :cc and is_current"
            ),
            {"cc": region},
        )
        row = result.first()
        return str(row[0]) if row else None

    # -- opt-outs --------------------------------------------------------------------------

    async def record_opt_out(
        self, *, remote: str, keyword: str | None, source: str, webhook_id: UUID | None
    ) -> None:
        await self._session.execute(
            text(
                """
                insert into public.sms_opt_outs
                    (remote_phone, platform_number, is_opted_out, source, keyword,
                     source_webhook_id, opted_out_at)
                values (cast(:r as public.e164), null, true, :source, :kw, :wh, now())
                on conflict (remote_phone, (coalesce(platform_number::text, ''))) do update
                   set is_opted_out = true, opted_in_at = null, lift_source = null,
                       lifted_by = null, lift_reason = null, source = excluded.source,
                       keyword = excluded.keyword, source_webhook_id = excluded.source_webhook_id,
                       opted_out_at = now()
                """
            ),
            {"r": remote, "source": source, "kw": keyword, "wh": webhook_id},
        )

    async def lift_opt_out(self, remote: str) -> bool:
        result = await self._session.execute(
            text(
                "update public.sms_opt_outs set is_opted_out = false, opted_in_at = now(), "
                "lift_source = 'recipient_keyword' "
                "where remote_phone = cast(:r as public.e164) and is_opted_out returning id"
            ),
            {"r": remote},
        )
        return result.first() is not None
