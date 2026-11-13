"""Administration of the SMS subsystem (Module J, FR-ADMIN-003/005/009/013/014).

Secrets never appear here: provider rows are returned without secret_ref and credentials are
reported only as configured or not. Every change is audit-logged with the administrator.
"""

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    UnprocessableError,
)
from app.core.privacy import mask_phone
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.integrations.sms.errors import reason_for_any
from app.integrations.sms.mock import MockSmsProvider
from app.modules.audit.service import AuditLogger
from app.modules.sms.admin_repository import AdminSmsRepository
from app.modules.sms.gateway import SmsGateway
from app.modules.sms.numbers import dial_code_for
from app.modules.sms.schemas import SimulateInboundRequest

_E164 = re.compile(r"^\+[1-9][0-9]{6,14}$")
_SENDER_ID = re.compile(r"^[A-Za-z0-9 ]{1,11}$")
RegistrationStatus = Literal["not_required", "not_registered", "pending", "registered"]
Support = Literal["unsupported", "requires_verification", "supported"]
NumberType = Literal["mobile", "fixed_line_or_mobile", "fixed_line", "voip"]


class ProviderAdminOut(BaseModel):
    id: UUID
    provider: str
    display_name: str
    mode: Literal["simulation", "live"]
    is_active: bool
    is_running: bool
    credentials_configured: bool
    sender_registration_status: str
    webhook_path: str | None
    max_retry_attempts: int
    retry_base_seconds: int
    retry_cap_seconds: int
    retry_multiplier: float
    sender_numbers: list[str]
    live_confirmed_at: datetime | None
    live_confirmed_environment: str | None


class ProviderUpdate(BaseModel):
    # extra=forbid: a request that tries to send a secret field is rejected, not ignored.
    model_config = ConfigDict(extra="forbid")

    sender_registration_status: RegistrationStatus | None = None
    max_retry_attempts: Annotated[int, Field(ge=1, le=10)] | None = None
    retry_base_seconds: Annotated[int, Field(ge=1, le=3600)] | None = None
    retry_cap_seconds: Annotated[int, Field(ge=1, le=86400)] | None = None
    retry_multiplier: Annotated[float, Field(ge=1, le=10)] | None = None
    sender_numbers: Annotated[list[str], Field(max_length=50)] | None = None


class ActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Typing the environment name is the explicit operator confirmation for live SMS.
    confirm_environment: str = Field(max_length=40)


class PausedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paused: bool


class CapabilityProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sender_id: str | None = None
    sender_number: str | None = None


class CapabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_name: str = Field(min_length=1, max_length=100)
    outbound_support: Support
    inbound_support: Support
    alphanumeric_sender_allowed: bool
    registered_sender_required: bool
    registered_sender_status: RegistrationStatus
    content_restrictions: str | None = Field(default=None, max_length=500)
    credit_multiplier: Decimal = Field(default=Decimal(1), gt=0, le=1000)
    max_segments: int = Field(default=10, ge=1, le=10)
    price_units_per_segment: int | None = Field(default=None, ge=0)
    supported_number_types: list[NumberType] = Field(min_length=1)
    consent_required: bool = True
    notes: str | None = Field(default=None, max_length=1000)
    provider_settings: CapabilityProviderSettings = CapabilityProviderSettings()
    # The administrator attests that provider verification evidence exists.
    verified: bool = False


class CapabilityAdminOut(BaseModel):
    country_code: str
    country_name: str
    dial_code: int
    version: int
    outbound_support: str
    inbound_support: str
    alphanumeric_sender_allowed: bool
    registered_sender_required: bool
    registered_sender_status: str
    content_restrictions: str | None
    credit_multiplier: float
    max_segments: int
    price_units_per_segment: int | None
    supported_number_types: list[str]
    consent_required: bool
    notes: str | None
    verified: bool


class StatusCount(BaseModel):
    status: str
    is_simulated: bool
    total: int


class FailureRow(BaseModel):
    message_id: UUID
    created_at: datetime
    status: str
    is_simulated: bool
    attempts: int
    failure_class: str | None
    failure_code: str | None
    reason: str
    masked_recipient: str


class MonitoringOut(BaseModel):
    mode: Literal["simulation", "live"]
    provider: str
    outbound_paused: bool
    dispatch_paused_by_configuration_error: bool
    queue_depth: int
    last_24h: list[StatusCount]
    delivery_rate: float | None
    failure_rate: float | None
    unrouted_inbound: int
    webhook_processing_failures: int
    webhook_orphaned: int
    webhook_signature_rejections: int
    opt_outs: int
    recent_failures: list[FailureRow]


class UnroutedOut(BaseModel):
    id: UUID
    received_at: datetime
    is_simulated: bool
    masked_sender: str
    masked_platform_number: str
    retained_until: datetime


class SimulateInboundOut(BaseModel):
    duplicate: bool
    routing_result: str | None


def _capability_out(row: dict[str, Any]) -> CapabilityAdminOut:
    return CapabilityAdminOut(
        country_code=row["country_code"],
        country_name=row["country_name"],
        dial_code=dial_code_for(row["country_code"]),
        version=row["version"],
        outbound_support=row["outbound_support"],
        inbound_support=row["inbound_support"],
        alphanumeric_sender_allowed=row["alphanumeric_sender_allowed"],
        registered_sender_required=row["registered_sender_required"],
        registered_sender_status=row["registered_sender_status"],
        content_restrictions=row["content_restrictions"],
        credit_multiplier=float(row["credit_multiplier"]),
        max_segments=row["max_segments"],
        price_units_per_segment=row["price_units_per_segment"],
        supported_number_types=list(row["supported_number_types"]),
        consent_required=row["consent_required"],
        notes=row["notes"],
        verified=row["verified_at"] is not None,
    )


class AdminSmsService:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        gateway: SmsGateway,
        audit: AuditLogger,
    ) -> None:
        self._settings = settings
        self._db = database
        self._gateway = gateway
        self._audit = audit

    @property
    def _provider_name(self) -> str:
        return self._gateway.provider.name

    def _credentials_configured(self, provider: str) -> bool:
        if provider == "mock":
            return True
        return bool(self._settings.twilio_account_sid and self._settings.twilio_auth_token)

    # -- providers -------------------------------------------------------------------------

    async def providers(self) -> list[ProviderAdminOut]:
        async with self._db.transaction() as session:
            rows = await AdminSmsRepository(session).providers()
        out: list[ProviderAdminOut] = []
        for row in rows:
            numbers = (row["settings"] or {}).get("sender_numbers", [])
            out.append(
                ProviderAdminOut(
                    id=row["id"],
                    provider=row["provider"],
                    display_name=row["display_name"],
                    mode=row["mode"],
                    is_active=row["is_active"],
                    is_running=row["provider"] == self._provider_name,
                    credentials_configured=self._credentials_configured(row["provider"]),
                    sender_registration_status=row["sender_registration_status"],
                    webhook_path=row["webhook_path"],
                    max_retry_attempts=row["max_retry_attempts"],
                    retry_base_seconds=row["retry_base_seconds"],
                    retry_cap_seconds=row["retry_cap_seconds"],
                    retry_multiplier=float(row["retry_multiplier"]),
                    sender_numbers=[mask_phone(n) for n in numbers if isinstance(n, str)],
                    live_confirmed_at=row["live_confirmed_at"],
                    live_confirmed_environment=row["live_confirmed_environment"],
                )
            )
        return out

    async def update_provider(
        self, admin: AuthenticatedUser, provider_id: UUID, request: ProviderUpdate, ip: str | None
    ) -> list[ProviderAdminOut]:
        values = request.model_dump(exclude_none=True)
        if "sender_numbers" in values:
            numbers = values["sender_numbers"]
            if any(not _E164.fullmatch(n) for n in numbers) or len(set(numbers)) != len(numbers):
                raise UnprocessableError(
                    "Sender numbers must be unique numbers in international format.",
                    code="invalid_sender_numbers",
                )
        async with self._db.transaction() as session:
            repository = AdminSmsRepository(session)
            if await repository.provider(provider_id) is None:
                raise NotFoundError("Provider not found.")
            try:
                await repository.update_provider(provider_id, values)
            except IntegrityError as exc:
                raise UnprocessableError(
                    "Those retry settings are not valid.", code="invalid_provider_settings"
                ) from exc
            await self._audit.record(
                session,
                category="admin",
                action="sms.provider_updated",
                actor_id=admin.id,
                actor_role=admin.role,
                target_type="provider",
                target_id=str(provider_id),
                ip=ip,
                metadata={"fields": sorted(values)},
            )
        return await self.providers()

    async def activate(
        self, admin: AuthenticatedUser, provider_id: UUID, request: ActivateRequest, ip: str | None
    ) -> list[ProviderAdminOut]:
        async with self._db.transaction() as session:
            repository = AdminSmsRepository(session)
            row = await repository.provider(provider_id)
            if row is None:
                raise NotFoundError("Provider not found.")
            if row["provider"] != self._provider_name:
                # Mode is startup configuration: it needs a redeploy, not a click.
                raise ConflictError(
                    "This provider is not the one the server was started with. "
                    "Change the deployment configuration and restart.",
                    code="provider_not_running",
                )
            if row["mode"] == "live":
                if not self._settings.sms_live_confirmed:
                    raise PermissionDeniedError(
                        "Live SMS is not confirmed in this environment's configuration.",
                        code="live_not_confirmed",
                    )
                if request.confirm_environment != self._settings.app_env:
                    raise UnprocessableError(
                        f"Type the environment name ({self._settings.app_env}) to confirm "
                        "live SMS.",
                        code="environment_mismatch",
                    )
            await repository.activate_provider(
                provider_id,
                confirm_by=admin.id if row["mode"] == "live" else None,
                environment=self._settings.app_env if row["mode"] == "live" else None,
            )
            await self._audit.record(
                session,
                category="admin",
                action="sms.provider_activated",
                actor_id=admin.id,
                actor_role=admin.role,
                target_type="provider",
                target_id=str(provider_id),
                ip=ip,
                metadata={"mode": row["mode"], "environment": self._settings.app_env},
            )
        return await self.providers()

    async def set_paused(self, admin: AuthenticatedUser, paused: bool, ip: str | None) -> bool:
        async with self._db.transaction() as session:
            await AdminSmsRepository(session).set_setting("sms_outbound_paused", paused, admin.id)
            await self._audit.record(
                session,
                category="admin",
                action="sms.outbound_paused" if paused else "sms.outbound_resumed",
                actor_id=admin.id,
                actor_role=admin.role,
                target_type="setting",
                target_id="sms_outbound_paused",
                ip=ip,
                metadata={"paused": paused},
            )
        return paused

    # -- capabilities ----------------------------------------------------------------------

    async def capabilities(self) -> list[CapabilityAdminOut]:
        async with self._db.transaction() as session:
            rows = await AdminSmsRepository(session).capabilities()
        return [_capability_out(r) for r in rows]

    async def put_capability(
        self, admin: AuthenticatedUser, country_code: str, request: CapabilityUpdate, ip: str | None
    ) -> CapabilityAdminOut:
        code = country_code.upper()
        settings_json = request.provider_settings
        if settings_json.sender_id and not _SENDER_ID.fullmatch(settings_json.sender_id):
            raise UnprocessableError(
                "A sender ID is up to 11 letters, digits or spaces.", code="invalid_sender_id"
            )
        if settings_json.sender_number and not _E164.fullmatch(settings_json.sender_number):
            raise UnprocessableError(
                "Sender number must be in international format.", code="invalid_sender_number"
            )
        try:
            async with self._db.transaction() as session:
                repository = AdminSmsRepository(session)
                version = await repository.next_capability_version(code)
                await repository.retire_current_capability(code)
                await repository.insert_capability(
                    {
                        "country_code": code,
                        "country_name": request.country_name,
                        "version": version,
                        "outbound_support": request.outbound_support,
                        "inbound_support": request.inbound_support,
                        "alphanumeric_sender_allowed": request.alphanumeric_sender_allowed,
                        "registered_sender_required": request.registered_sender_required,
                        "registered_sender_status": request.registered_sender_status,
                        "content_restrictions": request.content_restrictions,
                        "credit_multiplier": request.credit_multiplier,
                        "max_segments": request.max_segments,
                        "notes": request.notes,
                        "price_units_per_segment": request.price_units_per_segment,
                        "supported_number_types": request.supported_number_types,
                        "consent_required": request.consent_required,
                        "provider_settings": settings_json.model_dump_json(exclude_none=True),
                        "verified": request.verified,
                        "admin": admin.id,
                    }
                )
                await self._audit.record(
                    session,
                    category="admin",
                    action="sms.capability_updated",
                    actor_id=admin.id,
                    actor_role=admin.role,
                    target_type="country",
                    target_id=code,
                    ip=ip,
                    metadata={
                        "version": version,
                        "outbound": request.outbound_support,
                        "inbound": request.inbound_support,
                        "verified": request.verified,
                    },
                )
                rows = [r for r in await repository.capabilities() if r["country_code"] == code]
        except IntegrityError as exc:
            # The database refuses unsafe combinations (supported without verification, a
            # Philippine route without a registration status, ...). Say which rule.
            raise UnprocessableError(
                _constraint_message(str(exc)), code="capability_rejected"
            ) from exc
        return _capability_out(rows[0])

    # -- monitoring ------------------------------------------------------------------------

    async def monitoring(self) -> MonitoringOut:
        async with self._db.transaction() as session:
            repository = AdminSmsRepository(session)
            counts = await repository.status_counts()
            depth = await repository.queue_depth()
            hooks = await repository.webhook_counts()
            rejected = await repository.rejected_webhooks()
            failures = await repository.recent_failures(20)
            paused = (await _setting(session, "sms_outbound_paused")) is True
        totals: dict[str, int] = {}
        for row in counts:
            totals[row["status"]] = totals.get(row["status"], 0) + int(row["total"])
        delivered = totals.get("delivered", 0)
        bad = totals.get("failed", 0) + totals.get("undelivered", 0)
        settled = delivered + bad
        return MonitoringOut(
            mode=self._gateway.provider.mode,
            provider=self._provider_name,
            outbound_paused=paused,
            dispatch_paused_by_configuration_error=self._gateway.engine.dispatch_paused,
            queue_depth=depth,
            last_24h=[
                StatusCount(
                    status=r["status"], is_simulated=r["is_simulated"], total=int(r["total"])
                )
                for r in counts
            ],
            delivery_rate=delivered / settled if settled else None,
            failure_rate=bad / settled if settled else None,
            unrouted_inbound=hooks["unrouted"],
            webhook_processing_failures=hooks["failed"],
            webhook_orphaned=hooks["orphaned"],
            webhook_signature_rejections=rejected,
            opt_outs=hooks["opt_outs"],
            recent_failures=[
                FailureRow(
                    message_id=r["id"],
                    created_at=r["created_at"],
                    status=r["status"],
                    is_simulated=r["is_simulated"],
                    attempts=r["attempt_number"],
                    failure_class=r["failure_class"],
                    failure_code=r["failure_code"],
                    reason=reason_for_any(r["failure_code"]),
                    masked_recipient=mask_phone(r["recipient_phone"]),
                )
                for r in failures
            ],
        )

    async def unrouted(self, page: int, page_size: int) -> tuple[list[UnroutedOut], int]:
        async with self._db.transaction() as session:
            rows, total = await AdminSmsRepository(session).unrouted(
                (page - 1) * page_size, page_size
            )
        return (
            [
                UnroutedOut(
                    id=r["id"],
                    received_at=r["received_at"],
                    is_simulated=r["is_simulated"],
                    masked_sender=mask_phone(r["sender"] or ""),
                    masked_platform_number=mask_phone(r["platform_number"] or ""),
                    retained_until=r["purge_after"],
                )
                for r in rows
            ],
            total,
        )

    # -- simulation ------------------------------------------------------------------------

    async def simulate_inbound(
        self, admin: AuthenticatedUser, request: SimulateInboundRequest, ip: str | None
    ) -> SimulateInboundOut:
        """FR-SMSRECV-013: a reply injected through the real, signed webhook path."""
        provider = self._gateway.provider
        if (
            not isinstance(provider, MockSmsProvider)
            or provider.mode != "simulation"
            or self._settings.app_env == "production"
        ):
            raise PermissionDeniedError(
                "Reply simulation is only available in simulation mode outside production.",
                code="simulation_unavailable",
            )
        if not _E164.fullmatch(request.from_phone) or not _E164.fullmatch(request.to_number):
            raise UnprocessableError(
                "Numbers must be in international format.", code="invalid_phone"
            )
        event_id = request.replay_id or f"SIM-IN-{uuid.uuid4().hex[:16]}"
        callback = provider.build_inbound_callback(
            from_phone=request.from_phone,
            to_number=request.to_number,
            body=request.body,
            message_id=event_id,
        )
        result = await self._gateway.webhooks.deliver_simulated(callback)
        async with self._db.transaction() as session:
            routing = await AdminSmsRepository(session).webhook_routing("mock", event_id)
            await self._audit.record(
                session,
                category="admin",
                action="sms.simulated_inbound",
                actor_id=admin.id,
                actor_role=admin.role,
                target_type="sms_recipient",
                target_id=mask_phone(request.from_phone),
                ip=ip,
                metadata={"duplicate": result.duplicate, "routing": routing or "pending"},
            )
        return SimulateInboundOut(duplicate=result.duplicate, routing_result=routing)


async def _setting(session: Any, key: str) -> Any:
    from app.modules.sms.repository import SmsRepository

    return await SmsRepository(session).setting(key)


def _constraint_message(error: str) -> str:
    rules = {
        "ck_sms_cap_verified_for_support": "A route can only be supported with verification.",
        "ck_sms_cap_registered_for_support": "Supported outbound needs a registered sender.",
        "ck_sms_cap_ph_registration": "The Philippines needs a sender registration status.",
        "ck_sms_cap_number_types": "Choose at least one valid number type.",
    }
    for name, message in rules.items():
        if name in error:
            return message
    return "Those capability settings are not allowed."
