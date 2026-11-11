"""Mobile number verification with a one-time code (FR-AUTH-008, FR-AUTH-012).

This is separate from email verification (Supabase Auth). Codes are generated here, stored
only as a keyed hash, delivered through OtpDelivery, and never logged.
"""

import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import phonenumbers

from app.core.config import Settings
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    UnprocessableError,
)
from app.core.hashing import constant_time_equal, keyed_hash
from app.core.privacy import mask_phone
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.integrations.otp_delivery import (
    OtpDelivery,
    OtpDeliveryUnavailableError,
    SimulatedInbox,
)
from app.modules.audit.service import AuditLogger
from app.modules.auth.models import PhoneNumber
from app.modules.auth.repositories import PhoneAlreadyVerifiedError, PhoneRepository
from app.modules.auth.schemas import (
    PhoneStartResponse,
    PhoneStatusResponse,
    SimulatedSmsMessage,
)
from app.modules.auth.service import AuthService, RequestMeta
from app.modules.rate_limits import service as limits
from app.modules.rate_limits.service import RateLimiter

OTP_TTL_SECONDS = 600
RESEND_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5

_UNUSABLE = "This number cannot be verified for this account. Try a different number."


def normalise_phone(raw: str) -> tuple[str, str]:
    """Return (E.164, ISO region). Requires a leading + and a valid, dialable number."""
    candidate = raw.strip().replace(" ", "").replace("-", "")
    if not candidate.startswith("+"):
        raise UnprocessableError(
            "Enter the number in international format, starting with + and the country code.",
            details={"problems": [{"field": "body.phone_number", "reason": "Not E.164"}]},
        )
    try:
        parsed = phonenumbers.parse(candidate, None)
    except phonenumbers.NumberParseException as exc:
        raise UnprocessableError(
            "That phone number is not valid.",
            details={"problems": [{"field": "body.phone_number", "reason": "Unparseable"}]},
        ) from exc
    region = phonenumbers.region_code_for_number(parsed)
    if not phonenumbers.is_valid_number(parsed) or not region or len(region) != 2:
        raise UnprocessableError(
            "That phone number is not valid.",
            details={"problems": [{"field": "body.phone_number", "reason": "Invalid number"}]},
        )
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164), region


class PhoneVerificationService:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        delivery: OtpDelivery,
        inbox: SimulatedInbox,
        limiter: RateLimiter,
        audit: AuditLogger,
        auth_service: AuthService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        code_factory: Callable[[], str] = lambda: f"{secrets.randbelow(1_000_000):06d}",
    ) -> None:
        self._settings = settings
        self._db = database
        self._delivery = delivery
        self._inbox = inbox
        self._limiter = limiter
        self._audit = audit
        self._auth = auth_service
        self._clock = clock
        self._new_code = code_factory

    @property
    def mode(self) -> str:
        return self._delivery.mode

    def _hash(self, row: PhoneNumber, code: str) -> str:
        return keyed_hash(self._settings, "otp", f"{row.id}:{code}")

    async def status(self, user: AuthenticatedUser) -> PhoneStatusResponse:
        async with self._db.transaction() as session:
            row = await PhoneRepository(session).verified_for_user(user.id, self.mode)
        return PhoneStatusResponse(
            verified=row is not None,
            masked=mask_phone(row.e164) if row else None,
            verification_mode=row.verification_mode if row else None,
            verified_at=row.verified_at if row else None,
            delivery_mode=self._delivery.mode,
        )

    async def start(
        self,
        user: AuthenticatedUser,
        raw_number: str,
        password: str | None,
        meta: RequestMeta,
    ) -> PhoneStartResponse:
        e164, region = normalise_phone(raw_number)
        mode = self.mode

        async with self._db.transaction() as session:
            phones = PhoneRepository(session)
            current = await phones.verified_for_user(user.id, mode)
            if current is not None and current.e164 == e164:
                raise ConflictError(
                    "This number is already verified on your account.", code="already_verified"
                )
            unusable = await phones.verified_elsewhere(e164, mode, user.id)
        if current is not None:
            # Replacing a verified number requires the password (FR-AUTH-012 AC1).
            if not password:
                raise PermissionDeniedError(
                    "Confirm your password to change your mobile number.",
                    code="reauthentication_required",
                )
            await self._auth.reauthenticate(user, password, meta)
        if unusable:
            raise ConflictError(_UNUSABLE, code="phone_unavailable")

        await self._limiter.hit(limits.OTP_SEND_PER_USER, str(user.id))
        now = self._clock()
        code = self._new_code()

        async with self._db.transaction() as session:
            phones = PhoneRepository(session)
            row = await phones.pending_for_update(user.id, e164, mode)
            if row is None:
                row = await phones.create_pending(
                    user_id=user.id, e164=e164, country_code=region, mode=mode
                )
            elif row.last_otp_sent_at and now - row.last_otp_sent_at < timedelta(
                seconds=RESEND_COOLDOWN_SECONDS
            ):
                wait = RESEND_COOLDOWN_SECONDS - int((now - row.last_otp_sent_at).total_seconds())
                raise BadRequestError(
                    f"Wait {wait} seconds before requesting another code.",
                    code="resend_cooldown",
                    details={"retry_after_seconds": wait},
                )
            row.otp_hash = self._hash(row, code)
            row.otp_expires_at = now + timedelta(seconds=OTP_TTL_SECONDS)
            row.otp_attempts = 0
            row.otp_sent_count = min(10, (row.otp_sent_count or 0) + 1)
            row.otp_window_started_at = row.otp_window_started_at or now
            row.last_otp_sent_at = now
            await phones.flush()
            # Deliver inside the transaction: if delivery fails, no usable code is stored.
            try:
                await self._delivery.deliver(
                    user_id=str(user.id), e164=e164, code=code, ttl_seconds=OTP_TTL_SECONDS
                )
            except OtpDeliveryUnavailableError as exc:
                raise ServiceUnavailableError(
                    "Text message delivery is not available right now. Nothing was sent.",
                    code="otp_delivery_unavailable",
                ) from exc
            await self._audit.record(
                session,
                category="auth",
                action="phone.otp_sent",
                actor_id=user.id,
                ip=meta.ip,
                metadata={"phone": mask_phone(e164), "mode": mode},
            )

        return PhoneStartResponse(
            masked=mask_phone(e164),
            verification_mode=mode,
            expires_in=OTP_TTL_SECONDS,
            resend_available_in=RESEND_COOLDOWN_SECONDS,
        )

    async def confirm(
        self, user: AuthenticatedUser, raw_number: str, code: str, meta: RequestMeta
    ) -> PhoneStatusResponse:
        e164, _ = normalise_phone(raw_number)
        await self._limiter.hit(limits.OTP_VERIFY_PER_USER, str(user.id))
        now = self._clock()
        mode = self.mode
        failure: BadRequestError | UnprocessableError | None = None

        async with self._db.transaction() as session:
            phones = PhoneRepository(session)
            row = await phones.pending_for_update(user.id, e164, mode)
            if row is None or row.otp_hash is None:
                failure = BadRequestError(
                    "Request a new code for this number.", code="otp_not_requested"
                )
            elif row.otp_expires_at is None or row.otp_expires_at <= now:
                row.otp_hash = None
                row.otp_expires_at = None
                failure = BadRequestError(
                    "This code has expired. Request a new one.", code="otp_expired"
                )
            elif not constant_time_equal(row.otp_hash, self._hash(row, code)):
                row.otp_attempts = min(MAX_ATTEMPTS, row.otp_attempts + 1)
                remaining = MAX_ATTEMPTS - row.otp_attempts
                if remaining <= 0:
                    row.otp_hash = None
                    row.otp_expires_at = None
                    failure = BadRequestError(
                        "Too many wrong codes. Request a new one.", code="otp_locked"
                    )
                else:
                    failure = UnprocessableError(
                        "That code is not correct.",
                        code="otp_invalid",
                        details={"attempts_remaining": remaining},
                    )
            else:
                # Release the previous number only now that the new one is proven (AC: FR-AUTH-012).
                await phones.release_verified(user.id, now, mode)
                try:
                    await phones.mark_verified(row, now)
                except PhoneAlreadyVerifiedError as exc:
                    raise ConflictError(_UNUSABLE, code="phone_unavailable") from exc
                await self._audit.record(
                    session,
                    category="auth",
                    action="phone.verified",
                    actor_id=user.id,
                    ip=meta.ip,
                    metadata={"phone": mask_phone(e164), "mode": mode},
                )
            await phones.flush()
            # Failed attempts must persist, so the transaction commits before raising.

        if failure is not None:
            await self._audit.record_standalone(
                category="auth",
                action="phone.verify",
                outcome="denied",
                actor_id=user.id,
                ip=meta.ip,
                metadata={"reason": failure.code},
            )
            raise failure
        self._inbox.clear(str(user.id))
        return await self.status(user)

    async def remove(self, user: AuthenticatedUser, password: str, meta: RequestMeta) -> None:
        await self._auth.reauthenticate(user, password, meta)
        async with self._db.transaction() as session:
            released = await PhoneRepository(session).release_verified(user.id, self._clock())
            if not released:
                raise NotFoundError("There is no verified number to remove.")
            await self._audit.record(
                session, category="auth", action="phone.removed", actor_id=user.id, ip=meta.ip
            )

    def simulated_inbox(self, user: AuthenticatedUser) -> list[SimulatedSmsMessage]:
        """Simulation only, never in production (FR-AUTH-008 step 4)."""
        if self._delivery.mode != "simulated" or self._settings.app_env == "production":
            raise NotFoundError("Resource not found.")
        offset = time.time()
        now = self._clock()
        return [
            SimulatedSmsMessage(
                to=message.masked_to,
                body=f"Your Chikka Reborn code is {message.code}. It expires in 10 minutes.",
                created_at=now - timedelta(seconds=offset - message.created_at),
                expires_at=now + timedelta(seconds=message.expires_at - offset),
            )
            for message in self._inbox.list_for(str(user.id))
        ]
