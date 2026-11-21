"""Administration dashboard (Module J).

Reads come from the real tables; nothing is estimated or invented. Every change runs in one
transaction together with its audit row. The caller's role is checked by the router dependency
(`AdminUserDep`), which reads it from the database, never from the request.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.privacy import mask_email, mask_phone
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.integrations.sms.errors import reason_for_any
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    AdminUserDetail,
    AdminUserRow,
    AiDayUsage,
    AiErrorCount,
    AiFeatureUsage,
    AiMetricsOut,
    AiStats,
    AuditLogRow,
    ConfigurationStatusOut,
    ConversationStats,
    CountryCapabilityOut,
    CreditBalanceOut,
    CreditLedgerStats,
    DashboardOut,
    DeliveryAttemptOut,
    DeliveryEventOut,
    Health,
    MessageStats,
    ProviderHealthOut,
    ProviderOverviewOut,
    RestrictionReason,
    SmsMessageDetail,
    SmsMessageRow,
    SmsModeStats,
    SmsStats,
    UserActivityOut,
    UserStats,
)
from app.modules.audit.service import AuditLogger
from app.modules.sms.admin_repository import AdminSmsRepository
from app.modules.sms.gateway import SmsGateway

_SENT_STATUSES = frozenset({"accepted", "sent", "delivered", "undelivered"})
_IN_PROGRESS_STATUSES = frozenset({"queued", "retrying", "accepted", "sent"})
_MIN_SETTLED_FOR_RATE_ALERT = 5
_LOW_DELIVERY_RATE = 0.5

Direction = Literal["outbound", "inbound"]


def _rate(delivered: int, failed: int, undelivered: int) -> float | None:
    settled = delivered + failed + undelivered
    return delivered / settled if settled else None


def _sms_mode_stats(rows: list[dict[str, Any]], simulated: bool) -> SmsModeStats:
    outbound: dict[str, int] = {}
    received = 0
    for row in rows:
        if row["is_simulated"] != simulated:
            continue
        if row["direction"] == "inbound":
            received += int(row["total"])
        else:
            outbound[row["status"]] = outbound.get(row["status"], 0) + int(row["total"])
    delivered = outbound.get("delivered", 0)
    failed = outbound.get("failed", 0)
    undelivered = outbound.get("undelivered", 0)
    return SmsModeStats(
        sent=sum(n for s, n in outbound.items() if s in _SENT_STATUSES),
        received=received,
        delivered=delivered,
        failed=failed,
        undelivered=undelivered,
        in_progress=sum(n for s, n in outbound.items() if s in _IN_PROGRESS_STATUSES),
        delivery_success_rate=_rate(delivered, failed, undelivered),
    )


def _user_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "masked_email": mask_email(row["email"]),
        "role": row["role"],
        "status": row["status"],
        "country_code": row["country_code"],
        "created_at": row["created_at"],
        "last_seen_at": row["last_seen_at"],
        "suspended_at": row["suspended_at"],
    }


def _sms_row(row: dict[str, Any]) -> SmsMessageRow:
    outbound = row["direction"] == "outbound"
    phone = row["recipient_phone"] if outbound else row["sender_phone"]
    code = row["failure_code"]
    return SmsMessageRow(
        id=row["id"],
        direction=row["direction"],
        status=row["status"],
        is_simulated=row["is_simulated"],
        created_at=row["created_at"],
        masked_phone=mask_phone(phone) if phone else None,
        user_id=row["sender_user_id"] if outbound else row["recipient_user_id"],
        segment_count=row["segment_count"],
        attempts=int(row["attempts"]),
        provider_message_id=row["provider_message_id"],
        failure_class=row["failure_class"],
        failure_code=code,
        failure_reason=reason_for_any(code) if code else None,
    )


class AdminService:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        gateway: SmsGateway | None,
        audit: AuditLogger,
    ) -> None:
        self._settings = settings
        self._db = database
        self._gateway = gateway
        self._audit = audit

    # -- dashboard -------------------------------------------------------------------------

    async def dashboard(self) -> DashboardOut:
        async with self._db.transaction() as session:
            repository = AdminRepository(session)
            users = await repository.user_stats()
            conversations = await repository.conversation_stats()
            chikka_messages = await repository.chikka_messages_sent()
            sms_rows = await repository.sms_counts()
            ai = await repository.ai_totals()
            credits = await repository.credit_activity()
        return DashboardOut(
            generated_at=datetime.now(UTC),
            users=UserStats(**{k: int(v) for k, v in users.items()}),
            conversations=ConversationStats(**{k: int(v) for k, v in conversations.items()}),
            messages=MessageStats(chikka_messages_sent=chikka_messages),
            sms=SmsStats(
                live=_sms_mode_stats(sms_rows, simulated=False),
                simulated=_sms_mode_stats(sms_rows, simulated=True),
            ),
            ai=_ai_stats(ai),
            credits=[
                CreditLedgerStats(
                    ledger_type=row["ledger_type"],
                    transactions=int(row["transactions"]),
                    units_granted=int(row["units_granted"]),
                    units_deducted=int(row["units_deducted"]),
                    units_refunded=int(row["units_refunded"]),
                    units_adjusted=int(row["units_adjusted"]),
                )
                for row in credits
            ],
        )

    # -- users -----------------------------------------------------------------------------

    async def users(
        self,
        *,
        search: str | None,
        status: str | None,
        role: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AdminUserRow], int]:
        async with self._db.transaction() as session:
            rows, total = await AdminRepository(session).users(
                search=search.strip() if search else None,
                status=status,
                role=role,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
        return [AdminUserRow(**_user_row(r)) for r in rows], total

    async def user_detail(
        self, admin: AuthenticatedUser, user_id: UUID, ip: str | None
    ) -> AdminUserDetail:
        async with self._db.transaction() as session:
            repository = AdminRepository(session)
            row = await repository.user(user_id)
            if row is None:
                raise NotFoundError("User not found.")
            phone = await repository.verified_phone(user_id)
            activity = await repository.user_activity(user_id)
            balances = await repository.credit_balances(user_id)
            await self._audit.record(
                session,
                category="admin",
                action="admin.user_viewed",
                actor_id=admin.id,
                actor_role=admin.role,
                target_type="user",
                target_id=str(user_id),
                ip=ip,
            )
        return AdminUserDetail(
            **_user_row(row),
            masked_verified_phone=mask_phone(phone) if phone else None,
            ai_enabled=row["ai_enabled"],
            deletion_requested_at=row["deletion_requested_at"],
            activity=UserActivityOut(**{k: int(v) for k, v in activity.items()}),
            credits=[
                CreditBalanceOut(
                    ledger_type=b["ledger_type"],
                    balance_units=int(b["balance_units"]),
                    reserved_units=int(b["reserved_units"]),
                )
                for b in balances
            ],
        )

    async def restrict_user(
        self,
        admin: AuthenticatedUser,
        user_id: UUID,
        reason: RestrictionReason,
        ip: str | None,
    ) -> AdminUserRow:
        """Suspend an ordinary active account and end all of its sessions."""
        refusal: tuple[str, str] | None = None
        row: dict[str, Any] | None = None
        async with self._db.transaction() as session:
            repository = AdminRepository(session)
            target = await repository.lock_profile(user_id)
            if target is None:
                raise NotFoundError("User not found.")
            refusal = _restriction_refusal(admin, target)
            if refusal is None:
                await repository.suspend(user_id)
                revoked = await repository.revoke_sessions(user_id)
                await self._audit.record(
                    session,
                    category="admin",
                    action="admin.user_restricted",
                    actor_id=admin.id,
                    actor_role=admin.role,
                    target_type="user",
                    target_id=str(user_id),
                    ip=ip,
                    metadata={"reason_code": reason, "sessions_revoked": revoked},
                )
                row = await repository.user(user_id)
        # Audited once the transaction has closed, because it held a lock on the profile row
        # that the audit row references.
        if refusal is not None:
            await self._deny(admin, "admin.user_restrict_refused", user_id, refusal, ip)
            raise ConflictError(refusal[1], code=refusal[0])
        if row is None:
            raise NotFoundError("User not found.")
        return AdminUserRow(**_user_row(row))

    async def reinstate_user(
        self, admin: AuthenticatedUser, user_id: UUID, ip: str | None
    ) -> AdminUserRow:
        refused = False
        row: dict[str, Any] | None = None
        async with self._db.transaction() as session:
            repository = AdminRepository(session)
            target = await repository.lock_profile(user_id)
            if target is None:
                raise NotFoundError("User not found.")
            if target["status"] == "suspended":
                await repository.reinstate(user_id)
                await self._audit.record(
                    session,
                    category="admin",
                    action="admin.user_reinstated",
                    actor_id=admin.id,
                    actor_role=admin.role,
                    target_type="user",
                    target_id=str(user_id),
                    ip=ip,
                )
                row = await repository.user(user_id)
            else:
                refused = True
        if refused:
            message = "Only suspended accounts can be reinstated."
            await self._deny(
                admin,
                "admin.user_reinstate_refused",
                user_id,
                ("account_not_suspended", message),
                ip,
            )
            raise ConflictError(message, code="account_not_suspended")
        if row is None:
            raise NotFoundError("User not found.")
        return AdminUserRow(**_user_row(row))

    async def _deny(
        self,
        admin: AuthenticatedUser,
        action: str,
        user_id: UUID,
        refusal: tuple[str, str],
        ip: str | None,
    ) -> None:
        # Own transaction: the caller's rolls back when the error is raised.
        await self._audit.record_standalone(
            category="admin",
            action=action,
            outcome="denied",
            actor_id=admin.id,
            actor_role=admin.role,
            target_type="user",
            target_id=str(user_id),
            ip=ip,
            metadata={"code": refusal[0]},
        )

    # -- SMS monitoring --------------------------------------------------------------------

    async def sms_messages(
        self,
        *,
        direction: Direction,
        status: str | None,
        is_simulated: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[SmsMessageRow], int]:
        async with self._db.transaction() as session:
            rows, total = await AdminRepository(session).sms_messages(
                direction=direction,
                status=status,
                is_simulated=is_simulated,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
        return [_sms_row(r) for r in rows], total

    async def sms_message(
        self, admin: AuthenticatedUser, message_id: UUID, ip: str | None
    ) -> SmsMessageDetail:
        async with self._db.transaction() as session:
            repository = AdminRepository(session)
            row = await repository.sms_message(message_id)
            if row is None:
                raise NotFoundError("Message not found.")
            deliveries = await repository.deliveries(message_id)
            events = await repository.delivery_events([d["id"] for d in deliveries])
            await self._audit.record(
                session,
                category="admin",
                action="admin.sms_message_viewed",
                actor_id=admin.id,
                actor_role=admin.role,
                target_type="message",
                target_id=str(message_id),
                ip=ip,
            )
        by_delivery: dict[UUID, list[DeliveryEventOut]] = {}
        for event in events:
            by_delivery.setdefault(event["delivery_id"], []).append(
                DeliveryEventOut(
                    source=event["source"],
                    provider_status=event["provider_status"],
                    normalised_status=event["normalised_status"],
                    applied=event["applied"],
                    ignore_reason=event["ignore_reason"],
                    received_at=event["received_at"],
                )
            )
        history = [
            DeliveryAttemptOut(
                attempt_number=d["attempt_number"],
                status=d["status"],
                provider_message_id=d["provider_message_id"],
                is_simulated=d["is_simulated"],
                failure_class=d["failure_class"],
                failure_code=d["failure_code"],
                failure_reason=reason_for_any(d["failure_code"]) if d["failure_code"] else None,
                is_permanent=d["is_permanent"],
                started_at=d["started_at"],
                next_attempt_at=d["next_attempt_at"],
                terminal_at=d["terminal_at"],
                events=by_delivery.get(d["id"], []),
            )
            for d in deliveries
        ]
        return SmsMessageDetail(**_sms_row(row).model_dump(), attempts_history=history)

    # -- providers -------------------------------------------------------------------------

    async def provider_overview(self) -> ProviderOverviewOut:
        async with self._db.transaction() as session:
            sms_repository = AdminSmsRepository(session)
            counts = await sms_repository.status_counts()
            depth = await sms_repository.queue_depth()
            hooks = await sms_repository.webhook_counts()
            rejected = await sms_repository.rejected_webhooks()
            capabilities = await sms_repository.capabilities()
            admin_repository = AdminRepository(session)
            active = await admin_repository.active_provider()
            paused = await admin_repository.outbound_paused()
        return ProviderOverviewOut(
            health=self._health(counts, depth, hooks, rejected, active, paused),
            configuration=self._configuration(),
            capabilities=[
                CountryCapabilityOut(
                    country_code=c["country_code"],
                    country_name=c["country_name"],
                    outbound_support=c["outbound_support"],
                    inbound_support=c["inbound_support"],
                    registered_sender_required=c["registered_sender_required"],
                    registered_sender_status=c["registered_sender_status"],
                    verified=c["verified_by"] is not None,
                )
                for c in capabilities
            ],
        )

    def _configuration(self) -> ConfigurationStatusOut:
        s = self._settings
        # Only whether something is configured. Names and values of secrets never leave here.
        return ConfigurationStatusOut(
            app_env=s.app_env,
            sms_provider_mode=s.sms_provider_mode,
            sms_live_confirmed=s.sms_live_confirmed,
            sms_worker_enabled=s.sms_worker_enabled,
            ai_provider_mode=s.ai_provider_mode,
            ai_provider_configured=s.ai_provider_mode == "mock"
            or bool(s.bedrock_region and s.bedrock_model_id and s.bedrock_api_key),
            email_provider_mode=s.email_provider_mode,
        )

    def _health(
        self,
        counts: list[dict[str, Any]],
        depth: int,
        hooks: dict[str, int],
        rejected: int,
        active: str | None,
        paused: bool,
    ) -> ProviderHealthOut:
        gateway = self._gateway
        mode = gateway.provider.mode if gateway else None
        running = gateway.provider.name if gateway else None
        simulated = mode == "simulation"
        totals: dict[str, int] = {}
        for row in counts:
            if row["is_simulated"] == simulated:
                totals[row["status"]] = totals.get(row["status"], 0) + int(row["total"])
        rate = _rate(
            totals.get("delivered", 0), totals.get("failed", 0), totals.get("undelivered", 0)
        )
        settled = sum(totals.get(s, 0) for s in ("delivered", "failed", "undelivered"))
        dispatch_paused = bool(gateway and gateway.engine.dispatch_paused)

        degraded: list[str] = []
        if dispatch_paused:
            degraded.append("Dispatch is stopped by a configuration error.")
        if gateway and active and running != active:
            degraded.append("The running provider differs from the active provider setting.")
        if (
            rate is not None
            and settled >= _MIN_SETTLED_FOR_RATE_ALERT
            and rate < _LOW_DELIVERY_RATE
        ):
            degraded.append("Fewer than half of settled messages were delivered in 24 hours.")
        if hooks["failed"] or hooks["orphaned"]:
            degraded.append("Some provider callbacks could not be processed.")
        if rejected:
            degraded.append("Provider callbacks with invalid signatures were rejected.")

        health: Health
        reasons: list[str]
        if gateway is None:
            health, reasons = "unavailable", ["The SMS engine is not running."]
        elif degraded:
            health, reasons = "degraded", degraded
        elif paused:
            health, reasons = "paused", ["Outbound SMS is paused by an administrator."]
        else:
            health, reasons = "healthy", []
        return ProviderHealthOut(
            health=health,
            reasons=reasons,
            mode=mode,
            running_provider=running,
            active_provider=active,
            credentials_configured=self._credentials_configured(running),
            outbound_paused=paused,
            dispatch_paused_by_configuration_error=dispatch_paused,
            queue_depth=depth,
            delivery_success_rate_24h=rate,
            webhook_failures_24h=hooks["failed"] + hooks["orphaned"],
            webhook_signature_rejections_24h=rejected,
        )

    def _credentials_configured(self, provider: str | None) -> bool:
        if provider is None:
            return False
        if provider == "mock":
            return True
        return bool(self._settings.twilio_account_sid and self._settings.twilio_auth_token)

    # -- AI monitoring ---------------------------------------------------------------------

    async def ai_metrics(self, window_days: int) -> AiMetricsOut:
        since = datetime.now(UTC) - timedelta(days=window_days)
        async with self._db.transaction() as session:
            repository = AdminRepository(session)
            features = await repository.ai_features(since)
            errors = await repository.ai_errors(since)
            daily = await repository.ai_daily(since)
        input_tokens = sum(int(f["input_tokens"]) for f in features)
        output_tokens = sum(int(f["output_tokens"]) for f in features)
        return AiMetricsOut(
            window_days=window_days,
            total_requests=sum(int(f["requests"]) for f in features),
            failed_requests=sum(int(f["failures"]) for f in features),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self._estimated_cost(input_tokens, output_tokens),
            features=[
                AiFeatureUsage(
                    feature=f["feature"],
                    requests=int(f["requests"]),
                    failures=int(f["failures"]),
                    accepted=int(f["accepted"]),
                    average_latency_ms=f["average_latency_ms"],
                    input_tokens=int(f["input_tokens"]),
                    output_tokens=int(f["output_tokens"]),
                )
                for f in features
            ],
            errors=[
                AiErrorCount(
                    outcome=e["outcome"], error_code=e["error_code"], count=int(e["count"])
                )
                for e in errors
            ],
            daily=[AiDayUsage(day=d["day"], requests=int(d["requests"])) for d in daily],
        )

    def _estimated_cost(self, input_tokens: int, output_tokens: int) -> float | None:
        price_in = self._settings.ai_cost_per_1k_input_usd
        price_out = self._settings.ai_cost_per_1k_output_usd
        if price_in is None or price_out is None:
            return None
        return round(input_tokens / 1000 * price_in + output_tokens / 1000 * price_out, 4)

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
        page: int,
        page_size: int,
    ) -> tuple[list[AuditLogRow], int]:
        async with self._db.transaction() as session:
            rows, total = await AdminRepository(session).audit_logs(
                category=category,
                action=action.strip() if action else None,
                outcome=outcome,
                actor_id=actor_id,
                since=since,
                until=until,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
        return [AuditLogRow(**r) for r in rows], total


def _ai_stats(row: dict[str, Any]) -> AiStats:
    return AiStats(**{k: int(v) for k, v in row.items()})


def _restriction_refusal(
    admin: AuthenticatedUser, target: dict[str, Any]
) -> tuple[str, str] | None:
    if target["id"] == admin.id:
        return ("cannot_restrict_self", "You cannot restrict your own account.")
    if target["role"] == "admin":
        return (
            "cannot_restrict_administrator",
            "Administrator accounts cannot be restricted here.",
        )
    if target["status"] != "active":
        return ("account_not_active", "Only active accounts can be restricted.")
    return None
