"""The SMS engine: dispatch, retries, status transitions and reconciliation (design sections 4, 8).

Nothing here runs inside a request handler. The worker calls it.

Rules that keep this safe:
* Prefer a missed retry over a duplicate SMS to a real person. A claim that started and never
  recorded an outcome is treated as ambiguous and is not resent.
* Only transient failures retry, with exponential backoff and jitter and a hard attempt limit.
  Asynchronous failures reported by callbacks are never resent automatically.
* Status moves forward only. The first terminal state wins. "accepted" is never "delivered".
* Credits (simulated demo credits only): the queued message holds its cost; the provider
  accepting it spends the hold; a permanent failure releases the hold or refunds the spend.
  Each step is idempotent per message, so retries and repeated callbacks never charge twice.
"""

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.privacy import mask_phone
from app.database.session import Database
from app.integrations.sms.base import (
    STATUS_RANK,
    ProviderError,
    SendRequest,
    SendResult,
    SmsProvider,
)
from app.integrations.sms.errors import OPT_OUT_CODES, reason_for_any
from app.modules.audit.service import AuditLogger
from app.modules.credits import ledger as credit_ledger
from app.modules.notifications.service import create_notification
from app.modules.sms.gateway_repository import GatewayRepository
from app.modules.sms.repository import ProviderConfig, SmsRepository
from app.modules.sms.retry import RetryPolicy, can_retry, delay_seconds
from app.modules.sms.views import render_message
from app.realtime.hub import RealtimeHub, event

logger = logging.getLogger(__name__)

LEASE_SECONDS = 60
FIRST_POLL_SECONDS = 300
MAX_POLL_INTERVAL = timedelta(hours=24)
STOP_POLLING_AFTER = timedelta(hours=72)
CONFIGURATION_RETRY_SECONDS = 60


@dataclass
class Effects:
    """Things to announce after the transaction commits."""

    updated: set[UUID] = field(default_factory=set)
    created: set[UUID] = field(default_factory=set)


@dataclass(frozen=True)
class StatusResult:
    changed: bool
    status: str


@dataclass(frozen=True)
class SendPlan:
    delivery_id: UUID
    request: SendRequest
    policy: RetryPolicy
    cfg: ProviderConfig


class SmsEngine:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        provider: SmsProvider,
        audit: AuditLogger,
        hub: RealtimeHub,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        rng: random.Random | None = None,
    ) -> None:
        self._settings = settings
        self._db = database
        self._provider = provider
        self._audit = audit
        self._hub = hub
        self._clock = clock
        self._rng = rng or random.Random()  # noqa: S311 - jitter, not security
        self._circuit_until: datetime | None = None

    def now(self) -> datetime:
        return self._clock()

    @property
    def dispatch_paused(self) -> bool:
        """True while a provider configuration error has paused dispatch."""
        return self._circuit_until is not None and self.now() < self._circuit_until

    # -- announcing ------------------------------------------------------------------------

    async def publish(self, effects: Effects) -> None:
        ids = sorted(effects.created | effects.updated, key=str)
        if not ids:
            return
        frames: list[tuple[UUID, dict[str, Any]]] = []
        async with self._db.transaction() as session:
            sms = SmsRepository(session)
            gateway = GatewayRepository(session)
            now = self.now()
            for row in await sms.messages_by_ids(ids):
                owner = await gateway.conversation_owner(row["conversation_id"])
                if owner is None:
                    continue
                kind = (
                    "sms.message.created" if row["id"] in effects.created else "sms.message.updated"
                )
                out = render_message(row, owner, now)
                frames.append(
                    (
                        owner,
                        event(
                            kind, {"message": out.model_dump(mode="json")}, row["conversation_id"]
                        ),
                    )
                )
        for owner, frame in frames:
            self._hub.publish([owner], frame)

    # -- dispatch --------------------------------------------------------------------------

    async def dispatch_due(self, limit: int = 10) -> int:
        now = self.now()
        if self._circuit_until is not None and now < self._circuit_until:
            return 0
        async with self._db.transaction() as session:
            claims = await GatewayRepository(session).claim_due(
                now, now + timedelta(seconds=LEASE_SECONDS), limit
            )
        for claim in claims:
            try:
                await self._dispatch_one(claim)
            except Exception:
                # The lease expires and the claim is then treated as ambiguous: no blind resend.
                logger.exception("sms dispatch failed", extra={"delivery_id": str(claim["id"])})
        return len(claims)

    async def _dispatch_one(self, claim: dict[str, Any]) -> None:
        effects = Effects()
        plan = await self._prepare(claim, effects)
        await self.publish(effects)
        if plan is None:
            return

        result: SendResult | None = None
        error: ProviderError | None = None
        try:
            result = await self._provider.send_message(plan.request)
        except ProviderError as exc:
            error = exc
        except Exception as exc:
            logger.exception("sms provider call crashed")
            error = ProviderError("ambiguous", "internal_error", "Unexpected provider failure")
            error.__cause__ = exc

        effects = Effects()
        async with self._db.transaction() as session:
            repo = GatewayRepository(session)
            ctx = await repo.delivery(plan.delivery_id)
            if ctx is None:  # pragma: no cover - rows are never deleted
                return
            if result is not None:
                await self._record_success(session, repo, ctx, plan, result, effects)
            elif error is not None and ctx["status"] == "queued":
                await self._record_error(session, repo, ctx, plan, error, effects)
        await self.publish(effects)

    async def _prepare(self, claim: dict[str, Any], effects: Effects) -> SendPlan | None:
        """Decide what to do with a claimed attempt. Returns a plan only when the provider
        should be called; otherwise the attempt was settled here."""
        async with self._db.transaction() as session:
            repo = GatewayRepository(session)
            ctx = await repo.delivery(claim["id"])
            if ctx is None or ctx["status"] != "queued":
                return None
            cfg = await SmsRepository(session).active_provider()
            now = self.now()
            if (
                cfg is None
                or cfg.id != ctx["provider_configuration_id"]
                or (cfg.provider != self._provider.name)
            ):
                # Provider switched while queued: hold, never send through a different mode.
                logger.error(
                    "queued sms belongs to an inactive provider",
                    extra={"delivery_id": str(ctx["id"])},
                )
                await repo.update_delivery(
                    ctx["id"],
                    {
                        "locked_until": None,
                        "started_at": None,
                        "next_attempt_at": now + timedelta(seconds=CONFIGURATION_RETRY_SECONDS),
                    },
                )
                return None
            policy = RetryPolicy(
                cfg.max_retry_attempts,
                cfg.retry_base_seconds,
                cfg.retry_cap_seconds,
                cfg.retry_multiplier,
            )

            if ctx["failure_class"] == "ambiguous":
                # The wait for evidence is over.
                await self._mark_failed(
                    session,
                    repo,
                    ctx,
                    failure_class="ambiguous",
                    code="outcome_unknown",
                    effects=effects,
                )
                return None
            if claim["previous_started_at"] is not None:
                # An earlier claim began and recorded no outcome: it may have reached the provider.
                await self._hold_ambiguous(repo, ctx, "outcome_unknown")
                self._log_attempt(ctx, "ambiguous_hold")
                return None
            age = (now - ctx["message_created_at"]).total_seconds()
            if age > self._settings.sms_queue_max_age_seconds:
                await self._mark_failed(
                    session,
                    repo,
                    ctx,
                    failure_class=ctx["failure_class"] or "transient",
                    code="queue_expired",
                    effects=effects,
                )
                return None

            sender = await repo.sender_for(ctx["sender_user_id"], ctx["recipient_phone"])
            if sender is None:
                settings = await repo.capability_provider_settings(ctx["capability_id"])
                configured = settings.get("sender_id")
                sender = configured if isinstance(configured, str) and configured else None
            if sender is None:
                await self._mark_failed(
                    session,
                    repo,
                    ctx,
                    failure_class="configuration",
                    code="no_sender",
                    effects=effects,
                )
                return None

            request = SendRequest(
                to=ctx["recipient_phone"],
                body=ctx["body"],
                sender=sender,
                correlation_id=ctx["id"],
                idempotency_key=str(ctx["idempotency_key"]),
                status_callback_url=self._callback_url(ctx["id"]),
            )
            return SendPlan(ctx["id"], request, policy, cfg)

    def _callback_url(self, delivery_id: UUID) -> str | None:
        base = self._settings.sms_public_base_url
        if not base:
            return None
        return (
            f"{base.rstrip('/')}/api/v1/webhooks/{self._provider.name}/status?sms_id={delivery_id}"
        )

    # -- outcomes --------------------------------------------------------------------------

    async def _record_success(
        self,
        session: AsyncSession,
        repo: GatewayRepository,
        ctx: dict[str, Any],
        plan: SendPlan,
        result: SendResult,
        effects: Effects,
    ) -> None:
        await repo.update_delivery(
            ctx["id"],
            {
                "provider_message_id": result.provider_message_id,
                "provider_response": dict(result.response),
                "locked_until": None,
            },
        )
        # A callback can overtake this transaction; the rank rule then ignores the lower status.
        await self.apply_status(
            session,
            repo,
            ctx,
            mapped=result.mapped_status,
            provider_status=result.provider_status,
            error_code=None,
            source="send_response",
            dedupe_key=f"send:{result.provider_status}",
            occurred_at=None,
            webhook_id=None,
            effects=effects,
        )
        await self._audit.record(
            session,
            category="sms",
            action="sms.dispatched",
            target_type="message",
            target_id=str(ctx["message_id"]),
            metadata={
                "delivery_id": str(ctx["id"]),
                "attempt": ctx["attempt_number"],
                "provider": self._provider.name,
                "mode": self._provider.mode,
                "provider_message_id": result.provider_message_id,
                "provider_status": result.provider_status,
                "recipient": mask_phone(ctx["recipient_phone"]),
            },
        )
        self._log_attempt(ctx, "accepted")

    async def _record_error(
        self,
        session: AsyncSession,
        repo: GatewayRepository,
        ctx: dict[str, Any],
        plan: SendPlan,
        error: ProviderError,
        effects: Effects,
    ) -> None:
        now = self.now()
        attempt = ctx["attempt_number"]
        failure_class = error.failure_class
        self._log_attempt(ctx, f"error:{failure_class}:{error.code}")
        await self._audit.record(
            session,
            category="sms",
            action="sms.attempt_failed",
            outcome="failure",
            target_type="message",
            target_id=str(ctx["message_id"]),
            metadata={
                "delivery_id": str(ctx["id"]),
                "attempt": attempt,
                "failure_class": failure_class,
                "code": error.code,
                "provider": self._provider.name,
                "recipient": mask_phone(ctx["recipient_phone"]),
            },
        )

        if can_retry(plan.policy, attempt, failure_class):
            delay = delay_seconds(plan.policy, attempt, self._rng, error.retry_after)
            await repo.update_delivery(
                ctx["id"],
                {
                    "status": "failed",
                    "failure_class": "transient",
                    "is_permanent": False,
                    "failure_code": error.code,
                    "failure_reason": reason_for_any(error.code),
                    "http_status": error.http_status,
                    "locked_until": None,
                    "next_attempt_at": None,
                },
            )
            await repo.insert_event(
                delivery_id=ctx["id"],
                webhook_id=None,
                dedupe_key=f"attempt{attempt}:failed",
                source="system",
                provider_status=None,
                normalised_status="failed",
                error_code=error.code,
                occurred_at=None,
                applied=True,
                ignore_reason=None,
            )
            await repo.insert_retry_attempt(ctx, now + timedelta(seconds=delay))
            effects.updated.add(ctx["message_id"])
        elif failure_class == "transient":
            await self._mark_failed(
                session,
                repo,
                ctx,
                failure_class="transient",
                code="retries_exhausted",
                effects=effects,
                http_status=error.http_status,
            )
        elif failure_class == "ambiguous":
            await self._hold_ambiguous(repo, ctx, "outcome_unknown")
        elif failure_class == "configuration":
            # Not the message's fault and not fixable by retrying: pause dispatch and tell the
            # operator. Messages stay queued until the queue-age limit expires them.
            logger.error(
                "sms provider configuration error: dispatch paused",
                extra={"error_code": error.code, "provider": self._provider.name},
            )
            self._circuit_until = now + timedelta(seconds=CONFIGURATION_RETRY_SECONDS)
            await repo.update_delivery(
                ctx["id"],
                {
                    "failure_class": "configuration",
                    "failure_code": error.code,
                    "failure_reason": reason_for_any(error.code),
                    "http_status": error.http_status,
                    "locked_until": None,
                    "started_at": None,
                    "next_attempt_at": now + timedelta(seconds=CONFIGURATION_RETRY_SECONDS),
                },
            )
        else:
            if error.code in OPT_OUT_CODES:
                await repo.record_opt_out(
                    remote=ctx["recipient_phone"],
                    keyword=None,
                    source="provider_block",
                    webhook_id=None,
                )
            await self._mark_failed(
                session,
                repo,
                ctx,
                failure_class="permanent",
                code=error.code,
                effects=effects,
                http_status=error.http_status,
            )

    async def _hold_ambiguous(
        self, repo: GatewayRepository, ctx: dict[str, Any], code: str
    ) -> None:
        """Keep the message queued, without resending, until a correlated callback proves what
        happened or the resolution window ends."""
        deadline = self.now() + timedelta(seconds=self._settings.sms_ambiguous_window_seconds)
        await repo.update_delivery(
            ctx["id"],
            {
                "failure_class": "ambiguous",
                "failure_code": code,
                "failure_reason": reason_for_any(code),
                "locked_until": None,
                "next_attempt_at": deadline,
            },
        )

    async def _mark_failed(
        self,
        session: AsyncSession,
        repo: GatewayRepository,
        ctx: dict[str, Any],
        *,
        failure_class: str,
        code: str,
        effects: Effects,
        http_status: int | None = None,
    ) -> None:
        await repo.update_delivery(
            ctx["id"],
            {
                "status": "failed",
                "failure_class": failure_class,
                "is_permanent": True,
                "failure_code": code,
                "failure_reason": reason_for_any(code),
                "http_status": http_status,
                "locked_until": None,
                "next_attempt_at": None,
            },
        )
        await repo.insert_event(
            delivery_id=ctx["id"],
            webhook_id=None,
            dedupe_key=f"attempt{ctx['attempt_number']}:failed",
            source="system",
            provider_status=None,
            normalised_status="failed",
            error_code=code,
            occurred_at=None,
            applied=True,
            ignore_reason=None,
        )
        await credit_ledger.settle_failed(session, ctx["message_id"], provider=self._provider.name)
        await self._notify_terminal(session, ctx, "failed")
        effects.updated.add(ctx["message_id"])
        await self._audit.record(
            session,
            category="sms",
            action="sms.failed",
            outcome="failure",
            target_type="message",
            target_id=str(ctx["message_id"]),
            metadata={
                "delivery_id": str(ctx["id"]),
                "attempt": ctx["attempt_number"],
                "failure_class": failure_class,
                "code": code,
                "recipient": mask_phone(ctx["recipient_phone"]),
            },
        )

    # -- status transitions ----------------------------------------------------------------

    async def apply_status(
        self,
        session: AsyncSession,
        repo: GatewayRepository,
        ctx: dict[str, Any],
        *,
        mapped: str | None,
        provider_status: str,
        error_code: str | None,
        source: str,
        dedupe_key: str,
        occurred_at: datetime | None,
        webhook_id: UUID | None,
        effects: Effects,
    ) -> StatusResult:
        """Apply one provider signal to a locked delivery attempt (design section 4.3).

        Every signal is recorded; `applied` says whether it changed anything and why not.
        """
        old = ctx["status"]
        if mapped is None:
            await repo.insert_event(
                delivery_id=ctx["id"],
                webhook_id=webhook_id,
                dedupe_key=dedupe_key,
                source=source,
                provider_status=provider_status,
                normalised_status=old,
                error_code=error_code,
                occurred_at=occurred_at,
                applied=False,
                ignore_reason="unknown_status",
            )
            logger.warning(
                "unknown provider status", extra={"provider_status": provider_status[:40]}
            )
            return StatusResult(False, old)

        correction = old == "failed" and ctx["failure_class"] == "ambiguous" and mapped != "queued"
        new_rank, old_rank = STATUS_RANK[mapped], STATUS_RANK[old]
        reason: str | None = None
        if not correction:
            if new_rank < old_rank:
                reason = "out_of_order"
            elif mapped == old:
                reason = "duplicate_status"
            elif new_rank == old_rank:
                reason = "terminal_conflict"

        inserted = await repo.insert_event(
            delivery_id=ctx["id"],
            webhook_id=webhook_id,
            dedupe_key=dedupe_key,
            source=source,
            provider_status=provider_status,
            normalised_status=mapped,
            error_code=error_code,
            occurred_at=occurred_at,
            applied=reason is None,
            ignore_reason=reason,
        )
        if not inserted:
            return StatusResult(False, old)
        if reason is not None:
            if reason == "terminal_conflict":
                logger.warning(
                    "conflicting terminal status ignored", extra={"delivery_id": str(ctx["id"])}
                )
            return StatusResult(False, old)

        now = self.now()
        stamp = occurred_at or now
        values: dict[str, Any] = {
            "status": mapped,
            "provider_status": provider_status,
            "locked_until": None,
            "accepted_at": ctx["accepted_at"] or now,
        }
        if mapped in ("sent", "delivered"):
            values["sent_at"] = ctx["sent_at"] or stamp
        if mapped == "delivered":
            values["delivered_at"] = stamp
        if mapped in ("failed", "undelivered"):
            code = error_code or mapped
            values.update(
                failure_class="permanent",
                is_permanent=True,
                failure_code=code,
                failure_reason=reason_for_any(code),
                next_attempt_at=None,
            )
        else:
            if ctx["failure_class"] is not None:
                values.update(
                    failure_class=None, is_permanent=False, failure_code=None, failure_reason=None
                )
            if mapped in ("accepted", "sent"):
                values["next_attempt_at"] = now + timedelta(seconds=FIRST_POLL_SECONDS)
            else:
                values["next_attempt_at"] = None
            if correction and mapped not in ("delivered", "undelivered", "failed"):
                values["terminal_at"] = None
        await repo.update_delivery(ctx["id"], values)
        if mapped in ("accepted", "sent", "delivered"):
            await credit_ledger.capture(session, ctx["message_id"], provider=self._provider.name)
        elif mapped in ("failed", "undelivered"):
            await credit_ledger.settle_failed(
                session, ctx["message_id"], provider=self._provider.name
            )
        if correction:
            await self._audit.record(
                session,
                category="sms",
                action="sms.status_corrected",
                target_type="message",
                target_id=str(ctx["message_id"]),
                metadata={"delivery_id": str(ctx["id"]), "from": old, "to": mapped},
            )
        if mapped in ("delivered", "failed", "undelivered"):
            await self._notify_terminal(session, ctx, mapped)
            await self._audit.record(
                session,
                category="sms",
                action=f"sms.{mapped}",
                outcome="success" if mapped == "delivered" else "failure",
                target_type="message",
                target_id=str(ctx["message_id"]),
                metadata={
                    "delivery_id": str(ctx["id"]),
                    "source": source,
                    "provider": self._provider.name,
                    "simulated": bool(ctx["is_simulated"]),
                    "recipient": mask_phone(ctx["recipient_phone"]),
                },
            )
        effects.updated.add(ctx["message_id"])
        return StatusResult(True, mapped)

    async def _notify_terminal(
        self, session: AsyncSession, ctx: dict[str, Any], status: str
    ) -> None:
        if ctx["sender_user_id"] is None:
            return
        prefix = "Simulated SMS" if ctx["is_simulated"] else "SMS"
        if status == "delivered":
            kind, title = "sms_delivered", f"{prefix} delivered"
        elif status == "undelivered":
            kind, title = "sms_failed", f"{prefix} could not be delivered"
        else:
            kind, title = "sms_failed", f"{prefix} could not be sent"
        await create_notification(
            session,
            user_id=ctx["sender_user_id"],
            notification_type=kind,  # type: ignore[arg-type]
            title=title,
            reference_type="message",
            reference_id=ctx["message_id"],
            dedupe_key=f"sms_status:{ctx['message_id']}:{kind}",
            now=self.now(),
        )

    # -- reconciliation --------------------------------------------------------------------

    async def reconcile(self, limit: int = 20) -> int:
        """Poll the provider for messages whose callbacks never arrived. A route without
        receipts stays "sent": nothing here invents "delivered"."""
        now = self.now()
        async with self._db.transaction() as session:
            due = await GatewayRepository(session).stale_for_poll(now, limit)
        for row in due:
            snapshot = None
            try:
                snapshot = await self._provider.get_message_status(row["provider_message_id"])
            except ProviderError as exc:
                logger.warning("sms status poll failed", extra={"error_code": exc.code})
            effects = Effects()
            async with self._db.transaction() as session:
                repo = GatewayRepository(session)
                ctx = await repo.delivery(row["id"])
                if ctx is None or ctx["status"] not in ("accepted", "sent"):
                    continue
                result = StatusResult(False, ctx["status"])
                if snapshot is not None:
                    result = await self.apply_status(
                        session,
                        repo,
                        ctx,
                        mapped=snapshot.mapped_status,
                        provider_status=snapshot.provider_status,
                        error_code=snapshot.error_code,
                        source="poll",
                        dedupe_key=f"poll:{snapshot.provider_status}",
                        occurred_at=None,
                        webhook_id=None,
                        effects=effects,
                    )
                if result.status in ("accepted", "sent"):
                    age = now - (ctx["accepted_at"] or ctx["message_created_at"])
                    nxt = (
                        None
                        if age > STOP_POLLING_AFTER
                        else now
                        + min(
                            MAX_POLL_INTERVAL, max(timedelta(seconds=FIRST_POLL_SECONDS), age * 2)
                        )
                    )
                    await repo.update_delivery(ctx["id"], {"next_attempt_at": nxt})
            await self.publish(effects)
        return len(due)

    # -- logging ---------------------------------------------------------------------------

    def _log_attempt(self, ctx: dict[str, Any], outcome: str) -> None:
        logger.info(
            "sms attempt",
            extra={
                "delivery_id": str(ctx["id"]),
                "attempt": ctx["attempt_number"],
                "provider": self._provider.name,
                "recipient": mask_phone(ctx["recipient_phone"]),
                "outcome": outcome,
            },
        )
