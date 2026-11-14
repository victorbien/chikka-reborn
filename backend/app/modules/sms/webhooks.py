"""Webhook intake and processing: delivery callbacks and inbound SMS (Module E).

Order of operations for every request, live or simulated, is the same:

1. size limit, per-IP rate limit
2. signature check over the raw bytes, before anything is parsed or stored (no bypass)
3. parse and validate the payload
4. persist the verified event; a repeated event id is acknowledged and does nothing
5. process it (routing, opt-out, status transition) and announce the result
6. answer 2xx. A processing failure after step 4 is retried by the worker; the provider is not
   asked to resend, which avoids retry storms.

Inbound fallback (FR-SMSRECV-010/011): a valid inbound SMS that matches no active reply route is
never dropped and never shown to anyone. It stays in provider_webhooks (server-only, kept at
least 90 days) with routing_result 'unrouted', is audit-logged with a masked sender, appears in
the administrator's unrouted queue, and gets no automatic reply.
"""

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    BadRequestError,
    PayloadTooLargeError,
    PermissionDeniedError,
    ServiceUnavailableError,
)
from app.core.privacy import mask_phone
from app.core.sanitize import clean_text
from app.database.session import Database
from app.integrations.sms.base import ProviderError, SimulatedCallback, SmsProvider, WebhookError
from app.modules.audit.service import AuditLogger
from app.modules.notifications.service import create_notification
from app.modules.rate_limits.service import Limit, RateLimiter
from app.modules.sms.engine import Effects, SmsEngine
from app.modules.sms.gateway_repository import GatewayRepository
from app.modules.sms.numbers import region_of
from app.modules.sms.optout import classify_keyword
from app.modules.sms.repository import SmsRepository
from app.modules.sms.segments import MAX_SEGMENTS, analyse

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 64 * 1024
MAX_INBOUND_CHARS = 1600
ORPHAN_GRACE = timedelta(minutes=10)
ORPHAN_RECHECK_SECONDS = 30
MAX_PROCESS_ATTEMPTS = 6
WEBHOOK_PER_IP = Limit("sms.webhook.ip", 600, 60, message="Too many webhook requests.")
_E164 = re.compile(r"^\+[1-9][0-9]{6,14}$")
_NO_TEXT = "(no text)"
_MEDIA = "(Media messages aren't supported. Ask them to send text.)"


@dataclass(frozen=True)
class WebhookResult:
    duplicate: bool


class WebhookService:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        provider: SmsProvider,
        engine: SmsEngine,
        limiter: RateLimiter,
        audit: AuditLogger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._db = database
        self._provider = provider
        self._engine = engine
        self._limiter = limiter
        self._audit = audit
        self._clock = clock

    # -- intake ----------------------------------------------------------------------------

    async def handle(
        self,
        *,
        kind: str,
        raw_body: bytes,
        headers: Mapping[str, str],
        url: str,
        query: Mapping[str, str],
        ip: str | None,
    ) -> WebhookResult:
        if len(raw_body) > MAX_BODY_BYTES:
            raise PayloadTooLargeError("Payload too large.")
        if ip is not None:
            await self._limiter.hit(WEBHOOK_PER_IP, ip)

        try:
            valid = await self._provider.validate_webhook(raw_body, headers, url)
        except ProviderError as exc:
            # Fails closed: unsigned traffic is never accepted because a secret is missing.
            logger.error("webhook validation unavailable", extra={"error_code": exc.code})
            raise ServiceUnavailableError(
                "Webhook validation is unavailable.", code="webhook_unavailable"
            ) from exc
        if not valid:
            await self._audit.record_standalone(
                category="sms",
                action="sms.webhook_rejected",
                outcome="denied",
                ip=ip,
                metadata={
                    "provider": self._provider.name,
                    "kind": kind,
                    "reason": "invalid_signature",
                },
            )
            logger.warning(
                "webhook rejected", extra={"provider": self._provider.name, "kind": kind}
            )
            raise PermissionDeniedError("Invalid signature.", code="invalid_signature")

        try:
            if kind == "inbound":
                inbound = await self._provider.parse_inbound_message(raw_body, headers)
                dedupe, pmid = inbound.dedupe_key, inbound.provider_message_id
                payload: dict[str, Any] = {
                    "from": inbound.from_phone,
                    "to": inbound.to_number,
                    "body": inbound.body,
                    "provider_message_id": pmid,
                    "media_count": inbound.media_count,
                    "received_at": inbound.received_at.isoformat(),
                }
            else:
                status = await self._provider.parse_status_callback(raw_body, headers, query)
                dedupe, pmid = status.dedupe_key, status.provider_message_id
                payload = {
                    "provider_message_id": pmid,
                    "status": status.provider_status,
                    "dedupe_key": dedupe,
                    "mapped_status": status.mapped_status,
                    "error_code": status.error_code,
                    "correlation_id": str(status.correlation_id) if status.correlation_id else None,
                    "occurred_at": status.occurred_at.isoformat() if status.occurred_at else None,
                }
        except WebhookError as exc:
            logger.warning(
                "malformed webhook", extra={"provider": self._provider.name, "kind": kind}
            )
            raise BadRequestError(
                "The webhook payload is malformed.", code="malformed_webhook"
            ) from exc

        now = self._clock()
        async with self._db.transaction() as session:
            repo = GatewayRepository(session)
            cfg_id = await repo.configuration_id(self._provider.name, self._provider.mode)
            webhook_id = await repo.insert_webhook(
                provider=self._provider.name,
                cfg_id=cfg_id,
                kind=kind,
                dedupe_key=dedupe,
                provider_message_id=pmid,
                payload=payload,
                is_simulated=self._provider.is_simulated,
                now=now,
            )
        if webhook_id is None:
            logger.info(
                "duplicate webhook ignored", extra={"provider": self._provider.name, "kind": kind}
            )
            return WebhookResult(duplicate=True)

        effects = await self.process(webhook_id)
        await self._engine.publish(effects)
        return WebhookResult(duplicate=False)

    async def deliver_simulated(self, callback: SimulatedCallback) -> WebhookResult:
        """Simulated callbacks take the real intake path, signature check included."""
        return await self.handle(
            kind=callback.kind,
            raw_body=callback.raw_body,
            headers=callback.headers,
            url="simulation://local",
            query={},
            ip=None,
        )

    # -- processing ------------------------------------------------------------------------

    async def process_pending(self, limit: int = 20) -> int:
        async with self._db.transaction() as session:
            ids = await GatewayRepository(session).pending_webhooks(self._clock(), limit)
        for webhook_id in ids:
            await self._engine.publish(await self.process(webhook_id))
        return len(ids)

    async def process(self, webhook_id: UUID) -> Effects:
        effects = Effects()
        try:
            async with self._db.transaction() as session:
                repo = GatewayRepository(session)
                webhook = await repo.webhook(webhook_id)
                if webhook is None or webhook["processing_status"] == "processed":
                    return effects
                if webhook["kind"] == "status":
                    await self._process_status(session, repo, webhook, effects)
                else:
                    await self._process_inbound(session, repo, webhook, effects)
        except _DuplicateInboundError:
            async with self._db.transaction() as session:
                await GatewayRepository(session).finish_webhook(
                    webhook_id, status="processed", routing_result="duplicate", now=self._clock()
                )
            return Effects()
        except Exception as exc:
            logger.exception("webhook processing failed", extra={"webhook_id": str(webhook_id)})
            await self._record_failure(webhook_id, exc)
            return Effects()
        return effects

    async def _record_failure(self, webhook_id: UUID, exc: Exception) -> None:
        try:
            async with self._db.transaction() as session:
                repo = GatewayRepository(session)
                webhook = await repo.webhook(webhook_id)
                if webhook is None:
                    return
                attempts = webhook["process_attempts"] + 1
                now = self._clock()
                retry_at = (
                    now + timedelta(seconds=min(600, 5 * 2**attempts))
                    if attempts < MAX_PROCESS_ATTEMPTS
                    else None
                )
                await repo.finish_webhook(
                    webhook_id,
                    status="failed",
                    error_code=type(exc).__name__[:60],
                    next_process_at=retry_at,
                    attempts_increment=1,
                    now=now,
                )
        except Exception:
            logger.exception("could not record webhook failure")

    # -- delivery callbacks ----------------------------------------------------------------

    async def _process_status(
        self,
        session: AsyncSession,
        repo: GatewayRepository,
        webhook: dict[str, Any],
        effects: Effects,
    ) -> None:
        payload = webhook["raw_payload"]
        cfg_id: UUID = webhook["provider_configuration_id"]
        now = self._clock()
        pmid: str = payload["provider_message_id"]
        delivery = await repo.delivery_by_provider_id(cfg_id, pmid)
        correlation = payload.get("correlation_id")
        if delivery is None and correlation:
            delivery = await repo.delivery_by_correlation(cfg_id, UUID(correlation))
            if delivery is not None and delivery["provider_message_id"] is None:
                # The callback overtook our own commit of the provider id: adopt it.
                await repo.update_delivery(delivery["id"], {"provider_message_id": pmid})
                delivery["provider_message_id"] = pmid
            elif delivery is not None and delivery["provider_message_id"] != pmid:
                await repo.finish_webhook(
                    webhook["id"], status="failed", error_code="provider_id_mismatch", now=now
                )
                return
        if delivery is None:
            if now - webhook["received_at"] > ORPHAN_GRACE:
                await repo.finish_webhook(
                    webhook["id"],
                    status="failed",
                    error_code="unknown_message",
                    now=now,
                    attempts_increment=1,
                )
                await self._audit.record(
                    session,
                    category="sms",
                    action="sms.status_orphaned",
                    outcome="failure",
                    metadata={"provider": self._provider.name, "provider_message_id": pmid},
                )
            else:
                await repo.finish_webhook(
                    webhook["id"],
                    status="orphaned",
                    attempts_increment=1,
                    now=now,
                    next_process_at=now + timedelta(seconds=ORPHAN_RECHECK_SECONDS),
                )
            return

        occurred = payload.get("occurred_at")
        await self._engine.apply_status(
            session,
            repo,
            delivery,
            mapped=payload.get("mapped_status"),
            provider_status=payload["status"],
            error_code=payload.get("error_code"),
            source="simulation" if webhook["is_simulated"] else "webhook",
            dedupe_key=payload["dedupe_key"],
            occurred_at=datetime.fromisoformat(occurred) if occurred else None,
            webhook_id=webhook["id"],
            effects=effects,
        )
        await repo.finish_webhook(
            webhook["id"],
            status="processed",
            delivery_id=delivery["id"],
            message_id=delivery["message_id"],
            now=now,
        )

    # -- inbound SMS -----------------------------------------------------------------------

    async def _process_inbound(
        self,
        session: AsyncSession,
        repo: GatewayRepository,
        webhook: dict[str, Any],
        effects: Effects,
    ) -> None:
        payload = webhook["raw_payload"]
        now = self._clock()
        sender: str = payload["from"]
        platform: str = payload["to"]
        pmid: str = payload["provider_message_id"]
        simulated = bool(webhook["is_simulated"])
        wid: UUID = webhook["id"]
        masked = mask_phone(sender)

        async def finish(
            routing: str | None,
            *,
            status: str = "processed",
            error: str | None = None,
            message_id: UUID | None = None,
        ) -> None:
            await repo.finish_webhook(
                wid,
                status=status,
                routing_result=routing,
                error_code=error,
                message_id=message_id,
                now=now,
            )

        if not _E164.fullmatch(sender) or not _E164.fullmatch(platform):
            await finish(None, status="ignored", error="invalid_number")
            await self._audit.record(
                session,
                category="sms",
                action="sms.inbound_ignored",
                outcome="failure",
                metadata={
                    "provider_message_id": pmid,
                    "reason": "invalid_number",
                    "simulated": simulated,
                },
            )
            return

        body = clean_text(str(payload.get("body", "")))
        keyword = classify_keyword(body)
        if keyword is not None and keyword[0] == "opt_out":
            await repo.record_opt_out(
                remote=sender, keyword=keyword[1], source="keyword", webhook_id=wid
            )
            for owner in await repo.route_owners_by_remote(sender):
                await create_notification(
                    session,
                    user_id=owner,
                    notification_type="system",
                    title="A recipient opted out of SMS",
                    body=f"{masked} replied with a stop request. You can no longer text them.",
                    reference_type=None,
                    reference_id=None,
                )
            await self._audit.record(
                session,
                category="consent",
                action="sms.opt_out_recorded",
                target_type="sms_recipient",
                target_id=masked,
                metadata={
                    "keyword": keyword[1],
                    "provider_message_id": pmid,
                    "simulated": simulated,
                },
            )
            await finish("opt_out")
            return
        if keyword is not None and keyword[0] == "opt_in" and await repo.lift_opt_out(sender):
            await self._audit.record(
                session,
                category="consent",
                action="sms.opt_in_recorded",
                target_type="sms_recipient",
                target_id=masked,
                metadata={
                    "keyword": keyword[1],
                    "provider_message_id": pmid,
                    "simulated": simulated,
                },
            )
            await finish("opt_out")
            return

        capability_state = await repo.inbound_capability(region_of(sender))
        mismatch = capability_state == "unsupported"
        route = await repo.route_owner(platform, sender)
        if route is None:
            await finish("unrouted")
            await self._audit.record(
                session,
                category="sms",
                action="sms.inbound_unrouted",
                outcome="failure",
                target_type="sms_recipient",
                target_id=masked,
                metadata={
                    "provider_message_id": pmid,
                    "simulated": simulated,
                    "capability_mismatch": mismatch,
                },
            )
            logger.warning("inbound sms has no route", extra={"sender": masked})
            return

        user_id, _ = route
        if not await repo.user_is_active(user_id):
            await finish("suppressed")
            await self._audit.record(
                session,
                category="sms",
                action="sms.inbound_suppressed",
                outcome="failure",
                target_type="sms_recipient",
                target_id=masked,
                metadata={"provider_message_id": pmid, "reason": "recipient_unavailable"},
            )
            return

        text_body = body[:MAX_INBOUND_CHARS]
        if not text_body:
            text_body = _MEDIA if int(payload.get("media_count") or 0) > 0 else _NO_TEXT
        info = analyse(text_body)
        blocked = await repo.is_blocked_phone(user_id, sender)
        conversation_id = await SmsRepository(session).get_or_create_conversation(user_id, sender)
        message_id = await repo.insert_inbound_message(
            conversation_id=conversation_id,
            remote=sender,
            body=text_body,
            truncated=len(body) > MAX_INBOUND_CHARS,
            encoding=info.encoding,
            char_count=info.characters,
            segment_count=max(1, min(MAX_SEGMENTS, info.segments)),
            is_simulated=simulated,
            suppressed=blocked,
        )
        cfg_id: UUID = webhook["provider_configuration_id"]
        receipt = await repo.insert_inbound_receipt(
            message_id=message_id,
            cfg_id=cfg_id,
            user_id=user_id,
            provider_message_id=pmid,
            is_simulated=simulated,
            now=now,
        )
        if receipt is None:
            # The same provider message arrived through another path: exactly-once effect.
            raise _DuplicateInboundError()

        if blocked:
            await finish("blocked", message_id=message_id)
        else:
            muted = await repo.conversation_muted(conversation_id, user_id)
            await repo.unarchive_unmuted(conversation_id, user_id)
            if not muted:
                prefix = "SIMULATED: " if simulated else ""
                await create_notification(
                    session,
                    user_id=user_id,
                    notification_type="sms_inbound",
                    title=f"{prefix}New SMS reply",
                    reference_type="message",
                    reference_id=message_id,
                    group_key=f"sms:{conversation_id}",
                    dedupe_key=f"sms_inbound:{message_id}",
                )
            effects.created.add(message_id)
            await finish("routed", message_id=message_id)
        await self._audit.record(
            session,
            category="sms",
            action="sms.inbound",
            target_type="message",
            target_id=str(message_id),
            metadata={
                "provider_message_id": pmid,
                "sender": masked,
                "matched_user": str(user_id),
                "simulated": simulated,
                "routing": "blocked" if blocked else "routed",
                "capability_mismatch": mismatch,
            },
        )


class _DuplicateInboundError(Exception):
    """Raised inside the processing transaction so the duplicate message row rolls back."""
