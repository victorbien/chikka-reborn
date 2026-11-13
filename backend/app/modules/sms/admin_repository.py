"""Administrator queries for SMS configuration and monitoring."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sms.repository import CAPABILITY_COLUMNS


class AdminSmsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- providers -------------------------------------------------------------------------

    async def providers(self) -> list[dict[str, Any]]:
        # secret_ref is deliberately not selected: even its name stays out of the API.
        result = await self._session.execute(
            text(
                "select id, provider, display_name, mode, is_active, sender_registration_status, "
                "webhook_path, max_retry_attempts, retry_base_seconds, retry_cap_seconds, "
                "retry_multiplier, settings, live_confirmed_at, live_confirmed_environment "
                "from public.provider_configurations order by mode, provider"
            )
        )
        return [dict(r) for r in result.mappings()]

    async def provider(self, provider_id: UUID) -> dict[str, Any] | None:
        result = await self._session.execute(
            text(
                "select id, provider, mode, is_active from public.provider_configurations "
                "where id = :id for update"
            ),
            {"id": provider_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def update_provider(self, provider_id: UUID, values: dict[str, Any]) -> None:
        allowed = {
            "sender_registration_status",
            "max_retry_attempts",
            "retry_base_seconds",
            "retry_cap_seconds",
            "retry_multiplier",
        }
        assignments = [f"{k} = :{k}" for k in values if k in allowed]
        params = {k: v for k, v in values.items() if k in allowed}
        params["id"] = provider_id
        if "sender_numbers" in values:
            assignments.append(
                "settings = settings || jsonb_build_object("
                "'sender_numbers', cast(:sender_numbers as jsonb))"
            )
            params["sender_numbers"] = json.dumps(values["sender_numbers"])
        if assignments:
            await self._session.execute(
                text(
                    "update public.provider_configurations set "  # noqa: S608
                    + ", ".join(assignments)
                    + " where id = :id"
                ),
                params,
            )

    async def activate_provider(
        self, provider_id: UUID, *, confirm_by: UUID | None, environment: str | None
    ) -> None:
        await self._session.execute(
            text(
                "update public.provider_configurations set is_active = false "
                "where is_active and id <> :id"
            ),
            {"id": provider_id},
        )
        await self._session.execute(
            text(
                """
                update public.provider_configurations
                   set is_active = true,
                       live_confirmed_at =
                           case when mode = 'live' then now() else live_confirmed_at end,
                       live_confirmed_by =
                           case when mode = 'live' then :by else live_confirmed_by end,
                       live_confirmed_environment =
                           case when mode = 'live' then :env else live_confirmed_environment end
                 where id = :id
                """
            ),
            {"id": provider_id, "by": confirm_by, "env": environment},
        )

    # -- capabilities ----------------------------------------------------------------------

    async def capabilities(self) -> list[dict[str, Any]]:
        result = await self._session.execute(
            text(
                f"select {CAPABILITY_COLUMNS}, version, is_current, verified_by "  # noqa: S608
                "from public.sms_country_capabilities where is_current order by country_name"
            )
        )
        return [dict(r) for r in result.mappings()]

    async def next_capability_version(self, country_code: str) -> int:
        result = await self._session.execute(
            text(
                "select coalesce(max(version), 0) + 1 from public.sms_country_capabilities "
                "where country_code = :cc"
            ),
            {"cc": country_code},
        )
        return int(result.scalar_one())

    async def retire_current_capability(self, country_code: str) -> None:
        await self._session.execute(
            text(
                "update public.sms_country_capabilities set is_current = false "
                "where country_code = :cc and is_current"
            ),
            {"cc": country_code},
        )

    async def insert_capability(self, values: dict[str, Any]) -> None:
        await self._session.execute(
            text(
                """
                insert into public.sms_country_capabilities
                    (country_code, country_name, version, is_current, outbound_support,
                     inbound_support, alphanumeric_sender_allowed, registered_sender_required,
                     registered_sender_status, content_restrictions, credit_multiplier,
                     max_segments, notes, price_units_per_segment, supported_number_types,
                     consent_required, provider_settings, verified_at, verified_by, created_by)
                values
                    (:country_code, :country_name, :version, true, :outbound_support,
                     :inbound_support, :alphanumeric_sender_allowed, :registered_sender_required,
                     :registered_sender_status, :content_restrictions, :credit_multiplier,
                     :max_segments, :notes, :price_units_per_segment,
                     cast(:supported_number_types as text[]), :consent_required,
                     cast(:provider_settings as jsonb),
                     case when :verified then now() end,
                     case when :verified then cast(:admin as uuid) end, :admin)
                """
            ),
            values,
        )

    # -- settings and monitoring -----------------------------------------------------------

    async def set_setting(self, key: str, value: Any, admin_id: UUID) -> None:
        await self._session.execute(
            text(
                "insert into public.system_settings (key, value, updated_by) "
                "values (:k, cast(:v as jsonb), :u) "
                "on conflict (key) do update set value = excluded.value, "
                "updated_by = excluded.updated_by"
            ),
            {"k": key, "v": json.dumps(value), "u": admin_id},
        )

    async def status_counts(self) -> list[dict[str, Any]]:
        result = await self._session.execute(
            text(
                "select status, is_simulated, count(*) as total from public.messages "
                "where channel = 'sms' and direction = 'outbound' "
                "and created_at > now() - interval '24 hours' "
                "group by status, is_simulated"
            )
        )
        return [dict(r) for r in result.mappings()]

    async def queue_depth(self) -> int:
        result = await self._session.execute(
            text(
                "select count(*) from public.messages where channel = 'sms' "
                "and status in ('queued', 'retrying')"
            )
        )
        return int(result.scalar_one())

    async def webhook_counts(self) -> dict[str, int]:
        result = await self._session.execute(
            text(
                """
                select
                  count(*) filter (where routing_result = 'unrouted') as unrouted,
                  count(*) filter (where processing_status = 'failed') as failed,
                  count(*) filter (where processing_status = 'orphaned') as orphaned,
                  count(*) filter (where routing_result = 'opt_out') as opt_outs
                from public.provider_webhooks
                where received_at > now() - interval '24 hours'
                """
            )
        )
        return {k: int(v) for k, v in result.mappings().one().items()}

    async def rejected_webhooks(self) -> int:
        result = await self._session.execute(
            text(
                "select count(*) from public.audit_logs "
                "where action = 'sms.webhook_rejected' and created_at > now() - interval '24 hours'"
            )
        )
        return int(result.scalar_one())

    async def recent_failures(self, limit: int) -> list[dict[str, Any]]:
        result = await self._session.execute(
            text(
                """
                select m.id, m.created_at, m.status, m.is_simulated, d.attempt_number,
                       d.failure_class, d.failure_code, d.recipient_phone
                from public.messages m
                join lateral (
                    select * from public.message_deliveries x
                    where x.message_id = m.id order by x.attempt_number desc limit 1
                ) d on true
                where m.channel = 'sms' and m.direction = 'outbound'
                  and m.status in ('failed', 'undelivered')
                order by m.created_at desc limit :limit
                """
            ),
            {"limit": limit},
        )
        return [dict(r) for r in result.mappings()]

    async def unrouted(self, offset: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        total = (
            await self._session.execute(
                text(
                    "select count(*) from public.provider_webhooks "
                    "where kind = 'inbound' and routing_result = 'unrouted'"
                )
            )
        ).scalar_one()
        result = await self._session.execute(
            text(
                "select id, received_at, is_simulated, raw_payload->>'from' as sender, "
                "raw_payload->>'to' as platform_number, purge_after "
                "from public.provider_webhooks "
                "where kind = 'inbound' and routing_result = 'unrouted' "
                "order by received_at desc limit :limit offset :offset"
            ),
            {"limit": limit, "offset": offset},
        )
        return [dict(r) for r in result.mappings()], int(total)

    async def webhook_routing(self, provider: str, dedupe_key: str) -> str | None:
        result = await self._session.execute(
            text(
                "select routing_result from public.provider_webhooks "
                "where provider = :p and kind = 'inbound' and dedupe_key = :k"
            ),
            {"p": provider, "k": dedupe_key},
        )
        row = result.first()
        return str(row[0]) if row and row[0] else None
