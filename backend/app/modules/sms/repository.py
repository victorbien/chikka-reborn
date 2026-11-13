"""Database access for the user-facing SMS flows. The service owns the transaction.

Raw SQL with bound parameters only. Reads of tables owned by other modules (profiles' verified
numbers, contacts, user blocks) are narrow lookups kept here until those modules expose
directory interfaces for them.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sms.capabilities import Capability


@dataclass(frozen=True)
class ProviderConfig:
    id: UUID
    provider: str
    mode: str
    is_active: bool
    max_retry_attempts: int
    retry_base_seconds: int
    retry_cap_seconds: int
    retry_multiplier: float
    settings: dict[str, Any]
    sender_registration_status: str
    live_confirmed_at: datetime | None

    @property
    def sender_numbers(self) -> list[str]:
        numbers = self.settings.get("sender_numbers", [])
        return [n for n in numbers if isinstance(n, str)] if isinstance(numbers, list) else []


PROVIDER_COLUMNS = """
    id, provider, mode, is_active, max_retry_attempts, retry_base_seconds, retry_cap_seconds,
    retry_multiplier, settings, sender_registration_status, live_confirmed_at
"""


def provider_from_row(row: Any) -> ProviderConfig:
    return ProviderConfig(
        id=row["id"],
        provider=row["provider"],
        mode=row["mode"],
        is_active=row["is_active"],
        max_retry_attempts=row["max_retry_attempts"],
        retry_base_seconds=row["retry_base_seconds"],
        retry_cap_seconds=row["retry_cap_seconds"],
        retry_multiplier=float(row["retry_multiplier"]),
        settings=row["settings"] or {},
        sender_registration_status=row["sender_registration_status"],
        live_confirmed_at=row["live_confirmed_at"],
    )


CAPABILITY_COLUMNS = """
    id, country_code, country_name, version, outbound_support, inbound_support,
    alphanumeric_sender_allowed, registered_sender_required, registered_sender_status,
    content_restrictions, credit_multiplier, max_segments, notes, price_units_per_segment,
    supported_number_types, consent_required, provider_settings, verified_at
"""


def capability_from_row(row: Any) -> Capability:
    return Capability(
        id=row["id"],
        version=row["version"],
        country_code=row["country_code"],
        country_name=row["country_name"],
        outbound_support=row["outbound_support"],
        inbound_support=row["inbound_support"],
        alphanumeric_sender_allowed=row["alphanumeric_sender_allowed"],
        registered_sender_required=row["registered_sender_required"],
        registered_sender_status=row["registered_sender_status"],
        content_restrictions=row["content_restrictions"],
        credit_multiplier=Decimal(row["credit_multiplier"]),
        max_segments=row["max_segments"],
        notes=row["notes"],
        price_units_per_segment=row["price_units_per_segment"],
        supported_number_types=tuple(row["supported_number_types"]),
        consent_required=row["consent_required"],
        provider_settings=row["provider_settings"] or {},
        verified=row["verified_at"] is not None,
    )


# One message with its latest delivery attempt. Used for lists, detail and realtime payloads.
MESSAGE_SELECT = """
    select m.id, m.conversation_id, m.seq, m.direction, m.body, m.status, m.status_version,
           m.is_simulated, m.segment_count, m.encoding, m.char_count, m.idempotency_key,
           m.created_at, m.sender_user_id,
           d.attempt_number, d.status as delivery_status, d.failure_class, d.is_permanent,
           d.failure_code, d.accepted_at, d.sent_at, d.delivered_at, d.next_attempt_at,
           pc.provider as provider
    from public.messages m
    left join lateral (
        select * from public.message_deliveries x
        where x.message_id = m.id order by x.attempt_number desc limit 1
    ) d on true
    left join public.provider_configurations pc on pc.id = d.provider_configuration_id
"""


class SmsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- configuration ---------------------------------------------------------------------

    async def active_provider(self) -> ProviderConfig | None:
        result = await self._session.execute(
            text(f"select {PROVIDER_COLUMNS} from public.provider_configurations where is_active")  # noqa: S608
        )
        row = result.mappings().first()
        return provider_from_row(row) if row else None

    async def setting(self, key: str) -> Any:
        result = await self._session.execute(
            text("select value from public.system_settings where key = :key"), {"key": key}
        )
        row = result.first()
        return row[0] if row else None

    async def capability(self, country_code: str) -> Capability | None:
        result = await self._session.execute(
            text(
                f"select {CAPABILITY_COLUMNS} from public.sms_country_capabilities "  # noqa: S608
                "where country_code = :cc and is_current"
            ),
            {"cc": country_code.upper()},
        )
        row = result.mappings().first()
        return capability_from_row(row) if row else None

    async def capabilities(self) -> list[Capability]:
        result = await self._session.execute(
            text(
                f"select {CAPABILITY_COLUMNS} from public.sms_country_capabilities "  # noqa: S608
                "where is_current order by country_name"
            )
        )
        return [capability_from_row(r) for r in result.mappings()]

    # -- sender eligibility ----------------------------------------------------------------

    async def has_verified_phone(self, user_id: UUID, verification_mode: str) -> bool:
        result = await self._session.execute(
            text(
                "select 1 from public.phone_numbers where user_id = :u "
                "and verification_mode = :m and status = 'verified'"
            ),
            {"u": user_id, "m": verification_mode},
        )
        return result.first() is not None

    async def has_blocked_phone(self, user_id: UUID, phone: str) -> bool:
        result = await self._session.execute(
            text(
                "select 1 from public.user_blocks where blocker_id = :u "
                "and blocked_phone = cast(:p as public.e164)"
            ),
            {"u": user_id, "p": phone},
        )
        return result.first() is not None

    # -- recipients ------------------------------------------------------------------------

    async def sms_contact(self, owner_id: UUID, contact_id: UUID) -> tuple[str, str] | None:
        """(E.164, display name) of the owner's SMS contact, or None."""
        result = await self._session.execute(
            text(
                "select phone_e164, display_name from public.contacts "
                "where id = :id and owner_id = :owner and contact_type = 'sms'"
            ),
            {"id": contact_id, "owner": owner_id},
        )
        row = result.first()
        return (row[0], row[1]) if row else None

    async def contacts_by_phone(
        self, owner_id: UUID, phones: list[str]
    ) -> dict[str, tuple[UUID, str]]:
        if not phones:
            return {}
        result = await self._session.execute(
            text(
                "select phone_e164, id, display_name from public.contacts "
                "where owner_id = :owner and contact_type = 'sms' "
                "and phone_e164::text = any(cast(:phones as text[]))"
            ),
            {"owner": owner_id, "phones": phones},
        )
        return {r[0]: (r[1], r[2]) for r in result}

    # -- consent and opt-out ---------------------------------------------------------------

    async def has_consent(self, user_id: UUID, recipient: str) -> bool:
        result = await self._session.execute(
            text(
                "select private.has_active_consent(:u, 'sms_sender_attestation', "
                "cast(:r as public.e164))"
            ),
            {"u": user_id, "r": recipient},
        )
        return bool(result.scalar_one())

    async def record_consent(
        self,
        *,
        user_id: UUID,
        recipient: str,
        decision: str,
        notice_version: str,
        ip_prefix: str | None,
    ) -> None:
        await self._session.execute(
            text(
                """
                insert into public.user_consents
                    (user_id, consent_type, notice_version, decision, recipient_phone, source,
                     ip_prefix)
                values
                    (:u, 'sms_sender_attestation', :version, :decision,
                     cast(:r as public.e164), 'compose', :ip)
                """
            ),
            {
                "u": user_id,
                "version": notice_version,
                "decision": decision,
                "r": recipient,
                "ip": ip_prefix,
            },
        )

    async def is_opted_out(self, remote_phone: str) -> bool:
        result = await self._session.execute(
            text(
                "select 1 from public.sms_opt_outs "
                "where remote_phone = cast(:p as public.e164) and is_opted_out"
            ),
            {"p": remote_phone},
        )
        return result.first() is not None

    # -- routing ---------------------------------------------------------------------------

    async def release_expired_routes(self, remote: str) -> None:
        await self._session.execute(
            text(
                "update public.sms_routes set status = 'released', released_at = now(), "
                "release_reason = 'expired' "
                "where status = 'active' and expires_at < now() "
                "and remote_number = cast(:r as public.e164)"
            ),
            {"r": remote},
        )

    async def route_platform_number(self, user_id: UUID, remote: str) -> str | None:
        result = await self._session.execute(
            text(
                "select platform_number from public.sms_routes "
                "where user_id = :u and remote_number = cast(:r as public.e164) "
                "and status = 'active' and expires_at >= now()"
            ),
            {"u": user_id, "r": remote},
        )
        row = result.first()
        return str(row[0]) if row else None

    async def refresh_route(self, user_id: UUID, remote: str, ttl_days: int) -> None:
        await self._session.execute(
            text(
                "update public.sms_routes set last_outbound_at = now(), "
                "expires_at = now() + make_interval(days => :days) "
                "where user_id = :u and remote_number = cast(:r as public.e164) "
                "and status = 'active'"
            ),
            {"u": user_id, "r": remote, "days": ttl_days},
        )

    async def numbers_in_use(self, remote: str) -> set[str]:
        result = await self._session.execute(
            text(
                "select platform_number from public.sms_routes "
                "where remote_number = cast(:r as public.e164) and status = 'active'"
            ),
            {"r": remote},
        )
        return {str(r[0]) for r in result}

    async def create_route(
        self, *, user_id: UUID, conversation_id: UUID, platform: str, remote: str, ttl_days: int
    ) -> bool:
        """False when another user took the pair first (the unique index decides)."""
        result = await self._session.execute(
            text(
                """
                insert into public.sms_routes
                    (user_id, conversation_id, platform_number, remote_number, expires_at)
                values (:u, :c, cast(:p as public.e164), cast(:r as public.e164),
                        now() + make_interval(days => :days))
                on conflict do nothing
                returning id
                """
            ),
            {"u": user_id, "c": conversation_id, "p": platform, "r": remote, "days": ttl_days},
        )
        return result.first() is not None

    # -- conversations and messages --------------------------------------------------------

    async def get_or_create_conversation(self, user_id: UUID, remote: str) -> UUID:
        result = await self._session.execute(
            text("select private.get_or_create_sms_conversation(:u, cast(:r as public.e164))"),
            {"u": user_id, "r": remote},
        )
        return UUID(str(result.scalar_one()))

    async def conversation_remote(self, user_id: UUID, conversation_id: UUID) -> str | None:
        """The remote number of an SMS conversation the user belongs to, else None."""
        result = await self._session.execute(
            text(
                "select c.remote_phone from public.conversations c "
                "join public.conversation_members cm on cm.conversation_id = c.id "
                "where c.id = :c and c.conversation_type = 'sms' "
                "and cm.user_id = :u and cm.left_at is null"
            ),
            {"c": conversation_id, "u": user_id},
        )
        row = result.first()
        return str(row[0]) if row else None

    async def find_by_key(self, user_id: UUID, key: UUID) -> dict[str, Any] | None:
        result = await self._session.execute(
            text(
                "select id, conversation_id, request_hash from public.messages "
                "where sender_user_id = :u and idempotency_key = :k"
            ),
            {"u": user_id, "k": key},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def insert_outbound_message(
        self,
        *,
        conversation_id: UUID,
        user_id: UUID,
        body: str,
        encoding: str,
        char_count: int,
        segment_count: int,
        key: UUID,
        request_hash: str,
        is_simulated: bool,
        capability_id: UUID | None,
    ) -> UUID:
        result = await self._session.execute(
            text(
                """
                insert into public.messages
                    (conversation_id, channel, direction, sender_user_id, body, encoding,
                     char_count, segment_count, status, idempotency_key, request_hash,
                     is_simulated, capability_id)
                values
                    (:c, 'sms', 'outbound', :u, :body, :enc, :chars, :segs, 'queued', :k, :h,
                     :sim, :cap)
                returning id
                """
            ),
            {
                "c": conversation_id,
                "u": user_id,
                "body": body,
                "enc": encoding,
                "chars": char_count,
                "segs": segment_count,
                "k": key,
                "h": request_hash,
                "sim": is_simulated,
                "cap": capability_id,
            },
        )
        return UUID(str(result.scalar_one()))

    async def insert_first_delivery(
        self,
        *,
        message_id: UUID,
        provider_configuration_id: UUID,
        recipient_phone: str,
        is_simulated: bool,
        next_attempt_at: datetime,
    ) -> UUID:
        result = await self._session.execute(
            text(
                """
                insert into public.message_deliveries
                    (message_id, attempt_number, channel, provider_configuration_id,
                     recipient_phone, status, is_simulated, next_attempt_at)
                values
                    (:m, 1, 'sms', :cfg, cast(:r as public.e164), 'queued', :sim, :due)
                returning id
                """
            ),
            {
                "m": message_id,
                "cfg": provider_configuration_id,
                "r": recipient_phone,
                "sim": is_simulated,
                "due": next_attempt_at,
            },
        )
        delivery_id = UUID(str(result.scalar_one()))
        await self._session.execute(
            text(
                "insert into public.message_delivery_events "
                "(delivery_id, dedupe_key, source, normalised_status, applied) "
                "values (:d, 'queued', 'system', 'queued', true)"
            ),
            {"d": delivery_id},
        )
        return delivery_id

    async def unarchive(self, conversation_id: UUID, user_id: UUID) -> None:
        await self._session.execute(
            text(
                "update public.conversation_members set is_archived = false "
                "where conversation_id = :c and user_id = :u"
            ),
            {"c": conversation_id, "u": user_id},
        )

    async def messages_by_ids(self, ids: list[UUID]) -> list[dict[str, Any]]:
        if not ids:
            return []
        result = await self._session.execute(
            text(MESSAGE_SELECT + " where m.id = any(cast(:ids as uuid[])) order by m.seq"),
            {"ids": ids},
        )
        return [dict(r) for r in result.mappings()]

    async def message_for_user(self, user_id: UUID, message_id: UUID) -> dict[str, Any] | None:
        """A message in one of the user's SMS conversations, as the user may see it."""
        result = await self._session.execute(
            text(
                MESSAGE_SELECT
                + """
                join public.conversation_members cm
                  on cm.conversation_id = m.conversation_id and cm.user_id = :u
                 and cm.left_at is null
                where m.id = :id and m.channel = 'sms' and m.suppressed_at is null
                  and m.seq > cm.cleared_before_seq
                """
            ),
            {"u": user_id, "id": message_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def message_events(self, message_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.execute(
            text(
                """
                select e.normalised_status as status, e.source, e.applied, e.occurred_at,
                       e.received_at
                from public.message_delivery_events e
                join public.message_deliveries d on d.id = e.delivery_id
                where d.message_id = :m order by e.received_at, d.attempt_number
                """
            ),
            {"m": message_id},
        )
        return [dict(r) for r in result.mappings()]

    async def messages_page(
        self, user_id: UUID, conversation_id: UUID, *, before_seq: int | None, limit: int
    ) -> tuple[list[dict[str, Any]], bool]:
        result = await self._session.execute(
            text(
                MESSAGE_SELECT
                + """
                join public.conversation_members cm
                  on cm.conversation_id = m.conversation_id and cm.user_id = :u
                where m.conversation_id = :c and m.channel = 'sms' and m.suppressed_at is null
                  and m.seq > cm.cleared_before_seq
                  and (cast(:before as bigint) is null or m.seq < :before)
                order by m.seq desc limit :limit
                """
            ),
            {"u": user_id, "c": conversation_id, "before": before_seq, "limit": limit + 1},
        )
        rows = [dict(r) for r in result.mappings()]
        more = len(rows) > limit
        return list(reversed(rows[:limit])), more

    async def conversations(
        self, user_id: UUID, *, archived: bool, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        base = """
            from public.conversation_members cm
            join public.conversations c on c.id = cm.conversation_id
            where cm.user_id = :u and cm.left_at is null and c.conversation_type = 'sms'
              and cm.is_archived = :archived
        """
        params: dict[str, Any] = {"u": user_id, "archived": archived}
        total = (await self._session.execute(text("select count(*) " + base), params)).scalar_one()
        result = await self._session.execute(
            text(
                """
                select c.id, c.remote_phone, c.last_message_at, cm.last_read_seq, cm.is_archived,
                       (cm.muted_indefinitely
                        or coalesce(cm.muted_until > now(), false)) as is_muted,
                       (select count(*) from public.messages x
                         where x.conversation_id = c.id and x.direction = 'inbound'
                           and x.suppressed_at is null
                           and x.seq > greatest(cm.last_read_seq,
                                           cm.cleared_before_seq)) as unread_count,
                       lm.body as last_body, lm.direction as last_direction,
                       lm.status as last_status, lm.is_simulated as last_is_simulated
                from public.conversation_members cm
                join public.conversations c on c.id = cm.conversation_id
                left join lateral (
                    select m.body, m.direction, m.status, m.is_simulated
                    from public.messages m
                    where m.conversation_id = c.id and m.suppressed_at is null
                      and m.seq > cm.cleared_before_seq
                    order by m.seq desc limit 1
                ) lm on true
                where cm.user_id = :u and cm.left_at is null and c.conversation_type = 'sms'
                  and cm.is_archived = :archived
                order by c.last_message_at desc nulls last, c.id
                limit :limit offset :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        return [dict(r) for r in result.mappings()], int(total)

    async def advance_read(self, user_id: UUID, conversation_id: UUID, up_to_seq: int) -> int:
        result = await self._session.execute(
            text(
                """
                update public.conversation_members cm
                   set last_read_seq = greatest(cm.last_read_seq,
                           least(:seq, (select last_seq from public.conversations
                                         where id = :c))),
                       last_read_at = now(), marked_unread = false
                 where cm.conversation_id = :c and cm.user_id = :u
                returning cm.last_read_seq
                """
            ),
            {"seq": up_to_seq, "c": conversation_id, "u": user_id},
        )
        return int(result.scalar_one())

    async def last_read_seq(self, user_id: UUID, conversation_id: UUID) -> int:
        result = await self._session.execute(
            text(
                "select last_read_seq from public.conversation_members "
                "where conversation_id = :c and user_id = :u"
            ),
            {"c": conversation_id, "u": user_id},
        )
        return int(result.scalar_one())

    async def unread_count(self, user_id: UUID, conversation_id: UUID) -> int:
        result = await self._session.execute(
            text(
                """
                select count(*) from public.messages m
                join public.conversation_members cm
                  on cm.conversation_id = m.conversation_id and cm.user_id = :u
                where m.conversation_id = :c and m.direction = 'inbound'
                  and m.suppressed_at is null
                  and m.seq > greatest(cm.last_read_seq, cm.cleared_before_seq)
                """
            ),
            {"u": user_id, "c": conversation_id},
        )
        return int(result.scalar_one())


def dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, default=str)
