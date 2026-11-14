"""Internet-to-SMS for users (Module D) and the user side of Module E.

The request handler never calls the provider. It validates, stores the message as `queued`
with one delivery attempt, wakes the worker and returns. Dispatch, retries, callbacks and
inbound processing live in engine.py and webhooks.py.

Policy pipeline (design section 5.1), all checked server-side on every send:
sender verified -> provider mode consistent -> destination valid -> country capability ->
message size -> recipient not blocked by you -> recipient not opted out -> consent recorded ->
rate limits -> sender number / reply route -> store. Nothing is queued if a step fails.
"""

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    UnprocessableError,
)
from app.core.privacy import ip_prefix, mask_phone
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.integrations.sms.base import SmsProvider
from app.modules.audit.service import AuditLogger
from app.modules.credits import ledger as credit_ledger
from app.modules.credits.ledger import InsufficientCreditsError
from app.modules.credits.service import balance_hint
from app.modules.rate_limits.service import Limit, RateLimiter
from app.modules.sms.capabilities import (
    Capability,
    Verdict,
    estimate_cost,
    evaluate,
)
from app.modules.sms.numbers import Destination, dial_code_for, parse_destination, region_of
from app.modules.sms.repository import ProviderConfig, SmsRepository
from app.modules.sms.schemas import (
    BlockerOut,
    ConsentOut,
    ConsentRequest,
    CostOut,
    CountryOut,
    DeliveryEventOut,
    QuoteOut,
    QuoteRequest,
    RecipientFields,
    RecipientOut,
    SegmentOut,
    SendSmsRequest,
    SmsConversationOut,
    SmsMessageDetail,
    SmsMessageOut,
    SmsMessagePage,
    SmsModeOut,
    SmsReadState,
)
from app.modules.sms.segments import MAX_SEGMENTS, SegmentInfo, analyse
from app.modules.sms.views import preview, render_message
from app.realtime.hub import RealtimeHub, event

logger = logging.getLogger(__name__)

_NOT_FOUND = "Conversation not found."
DEFAULT_PAGE = 50
MAX_PAGE = 100

SMS_SEND_PER_USER_DAY = Limit(
    "sms.send.user.day", 500, 86400, message="You've reached today's SMS limit."
)
SMS_SEND_PER_IP = Limit(
    "sms.send.ip", 60, 60, message="Too many SMS requests from this network. Please wait."
)


@dataclass(frozen=True)
class Recipient:
    destination: Destination
    contact_id: UUID | None = None
    display_name: str | None = None
    conversation_id: UUID | None = None


@dataclass(frozen=True)
class Blocker:
    code: str
    message: str
    status: int = 422


@dataclass
class Evaluation:
    cfg: ProviderConfig
    capability: Capability | None
    verdict: Verdict
    segment: SegmentInfo
    max_segments: int
    cost_units: int | None
    cost_source: str
    consent_required: bool
    consent_granted: bool
    opted_out: bool
    sender_verified: bool
    available_units: int = 0
    credit_threshold: int = 500
    blockers: list[Blocker] = field(default_factory=list)


def request_hash(destination: Destination, body: str) -> str:
    return hashlib.sha256(f"{destination.e164}\n{body}".encode()).hexdigest()


def _raise(blocker: Blocker) -> AppError:
    if blocker.status == 403:
        return PermissionDeniedError(blocker.message, code=blocker.code)
    if blocker.status == 503:
        return ServiceUnavailableError(blocker.message, code=blocker.code)
    if blocker.status == 402:
        return InsufficientCreditsError(blocker.message)
    return UnprocessableError(
        blocker.message,
        code=blocker.code,
        details={"problems": [{"field": "body", "reason": blocker.code}]},
    )


class SmsService:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        provider: SmsProvider,
        limiter: RateLimiter,
        audit: AuditLogger,
        hub: RealtimeHub,
        wake: Callable[[], None] = lambda: None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._db = database
        self._provider = provider
        self._limiter = limiter
        self._audit = audit
        self._hub = hub
        self._wake = wake
        self._clock = clock

    @property
    def _live(self) -> bool:
        return self._provider.mode == "live"

    @property
    def _verification_mode(self) -> str:
        return "live" if self._live else "simulated"

    # -- mode and capability ---------------------------------------------------------------

    async def _check_provider(self, repository: SmsRepository) -> ProviderConfig:
        """Fail loudly when configuration and database disagree. Never substitute a mode."""
        cfg = await repository.active_provider()
        if cfg is None:
            raise ServiceUnavailableError("SMS is not configured.", code="sms_unconfigured")
        if cfg.provider != self._provider.name or cfg.mode != self._provider.mode:
            logger.error(
                "sms provider mismatch",
                extra={"configured": self._provider.name, "database_active": cfg.provider},
            )
            raise ServiceUnavailableError(
                "SMS sending is paused until an operator fixes the provider configuration.",
                code="sms_mode_mismatch",
            )
        if self._live and cfg.live_confirmed_at is None:
            raise ServiceUnavailableError(
                "Live SMS has not been confirmed by an operator for this environment.",
                code="live_not_confirmed",
            )
        return cfg

    async def _is_paused(self, repository: SmsRepository) -> bool:
        return (await repository.setting("sms_outbound_paused")) is True

    async def status(self, user: AuthenticatedUser) -> SmsModeOut:
        async with self._db.transaction() as session:
            repository = SmsRepository(session)
            paused = await self._is_paused(repository)
            verified = await repository.has_verified_phone(user.id, self._verification_mode)
        simulated = self._provider.is_simulated
        return SmsModeOut(
            mode=self._provider.mode,
            provider=self._provider.name,
            is_simulated=simulated,
            outbound_paused=paused,
            sender_verified=verified,
            notice=(
                "Simulation mode: no real SMS is sent and nothing costs money."
                if simulated
                else "Live mode: messages are sent to real phones."
            ),
        )

    def _country_out(self, cap: Capability) -> CountryOut:
        verdict = evaluate(cap, number_type="mobile", live=self._live)
        price = cap.price_units_per_segment
        return CountryOut(
            country_code=cap.country_code,
            country_name=cap.country_name,
            dial_code=dial_code_for(cap.country_code),
            availability=verdict.availability,
            unavailable_reason=verdict.reason,
            outbound=cap.outbound_support,
            replies=verdict.replies,
            alphanumeric_sender_allowed=cap.alphanumeric_sender_allowed,
            registered_sender_required=cap.registered_sender_required,
            registered_sender_status=cap.registered_sender_status,
            supported_number_types=list(cap.supported_number_types),
            content_restrictions=cap.content_restrictions,
            consent_required=cap.consent_required,
            credits_per_segment=(
                float(price * cap.credit_multiplier) / 100 if price is not None else None
            ),
            max_segments=min(cap.max_segments, MAX_SEGMENTS),
            verified=cap.verified,
            notes=cap.notes,
        )

    async def countries(self) -> list[CountryOut]:
        async with self._db.transaction() as session:
            capabilities = await SmsRepository(session).capabilities()
        return [self._country_out(c) for c in capabilities]

    async def capability(self, *, country_code: str | None, phone_number: str | None) -> CountryOut:
        if (country_code is None) == (phone_number is None):
            raise UnprocessableError(
                "Provide either country_code or phone_number.", code="validation_error"
            )
        region = (
            country_code.upper()
            if country_code
            else region_of(parse_destination(phone_number or "").e164)
        )
        async with self._db.transaction() as session:
            cap = await SmsRepository(session).capability(region or "")
        if cap is None:
            raise NotFoundError(
                "We have no SMS information for this country. It is treated as unsupported.",
                code="country_unsupported",
            )
        return self._country_out(cap)

    # -- recipients ------------------------------------------------------------------------

    async def _resolve(
        self, repository: SmsRepository, user: AuthenticatedUser, fields: RecipientFields
    ) -> Recipient:
        if fields.contact_id is not None:
            contact = await repository.sms_contact(user.id, fields.contact_id)
            if contact is None:
                raise NotFoundError("Contact not found.")
            return Recipient(
                parse_destination(contact[0]), contact_id=fields.contact_id, display_name=contact[1]
            )
        if fields.conversation_id is not None:
            remote = await repository.conversation_remote(user.id, fields.conversation_id)
            if remote is None:
                raise NotFoundError(_NOT_FOUND)
            return Recipient(parse_destination(remote), conversation_id=fields.conversation_id)
        return Recipient(parse_destination(fields.to or "", fields.country_code))

    async def _evaluate(
        self,
        repository: SmsRepository,
        user: AuthenticatedUser,
        recipient: Recipient,
        body: str,
    ) -> Evaluation:
        cfg = await self._check_provider(repository)
        if await self._is_paused(repository):
            raise ServiceUnavailableError(
                "SMS sending is paused by an administrator.", code="sms_paused"
            )
        destination = recipient.destination
        capability = await repository.capability(destination.country_code)
        verdict = evaluate(capability, number_type=destination.number_type, live=self._live)
        segment = analyse(body)
        max_segments = min(capability.max_segments, MAX_SEGMENTS) if capability else MAX_SEGMENTS
        demo = await repository.setting("sms_demo_units_per_segment")
        cost = estimate_cost(
            capability,
            segment.segments,
            live=self._live,
            demo_units_per_segment=int(demo) if isinstance(demo, int) else None,
        )
        simulated = self._provider.is_simulated
        available, threshold = await repository.credit_state(user.id) if simulated else (0, 500)
        verified = await repository.has_verified_phone(user.id, self._verification_mode)
        opted_out = await repository.is_opted_out(destination.e164)
        consent_required = capability.consent_required if capability else True
        consent_granted = await repository.has_consent(user.id, destination.e164)

        blockers: list[Blocker] = []
        if not verified:
            blockers.append(
                Blocker(
                    "sender_not_verified",
                    "Verify your mobile number before sending SMS.",
                    403,
                )
            )
        if not verdict.allowed and verdict.reason_code and verdict.reason:
            blockers.append(Blocker(verdict.reason_code, verdict.reason))
        if segment.segments > max_segments:
            blockers.append(
                Blocker(
                    "message_too_long",
                    f"This message needs {segment.segments} segments. "
                    f"The limit for this destination is {max_segments}.",
                )
            )
        if await repository.has_blocked_phone(user.id, destination.e164):
            blockers.append(
                Blocker(
                    "user_blocked", "You blocked this number. Unblock it to send messages.", 403
                )
            )
        if opted_out:
            blockers.append(
                Blocker(
                    "recipient_opted_out",
                    "This person has opted out of messages, so we can't send to this number.",
                )
            )
        if consent_required and not consent_granted:
            blockers.append(
                Blocker(
                    "consent_required",
                    "Confirm you have this person's permission to text them before sending.",
                )
            )
        if simulated and cost.units is not None and cost.units > available:
            blockers.append(
                Blocker(
                    "insufficient_credits",
                    f"This message costs {cost.units / 100:.2f} demo credits and you have "
                    f"{max(available, 0) / 100:.2f}.",
                    402,
                )
            )
        return Evaluation(
            cfg=cfg,
            capability=capability,
            verdict=verdict,
            segment=segment,
            max_segments=max_segments,
            cost_units=cost.units,
            cost_source=cost.source,
            consent_required=consent_required,
            consent_granted=consent_granted,
            opted_out=opted_out,
            sender_verified=verified,
            available_units=available,
            credit_threshold=threshold,
            blockers=blockers,
        )

    def _quote_out(self, recipient: Recipient, evaluation: Evaluation) -> QuoteOut:
        destination = recipient.destination
        capability = evaluation.capability
        segment = evaluation.segment
        units = evaluation.cost_units
        return QuoteOut(
            balance=balance_hint(
                available_units=evaluation.available_units,
                cost_units=units,
                is_simulated=self._provider.is_simulated,
                threshold_units=evaluation.credit_threshold,
            ),
            recipient=RecipientOut(
                masked_phone=mask_phone(destination.e164),
                country_code=destination.country_code,
                country_name=capability.country_name if capability else None,
                number_type=destination.number_type,
                contact_id=recipient.contact_id,
                display_name=recipient.display_name,
                conversation_id=recipient.conversation_id,
            ),
            mode=self._provider.mode,
            is_simulated=self._provider.is_simulated,
            availability=evaluation.verdict.availability,
            replies=evaluation.verdict.replies,
            warnings=evaluation.verdict.warnings,
            segment=SegmentOut(
                encoding=segment.encoding,
                characters=segment.characters,
                units=segment.units,
                segments=segment.segments,
                per_segment=segment.per_segment,
                remaining_in_segment=segment.remaining_in_segment,
                max_segments=evaluation.max_segments,
                too_long=segment.segments > evaluation.max_segments,
            ),
            cost=CostOut(
                units=units,
                credits=None if units is None else units / 100,
                source=evaluation.cost_source,
            ),
            consent=ConsentOut(
                required=evaluation.consent_required,
                granted=evaluation.consent_granted,
                notice_version=self._settings.sms_attestation_version,
            ),
            recipient_opted_out=evaluation.opted_out,
            blockers=[BlockerOut(code=b.code, message=b.message) for b in evaluation.blockers],
            can_send=not evaluation.blockers and segment.segments >= 1,
        )

    async def quote(self, user: AuthenticatedUser, request: QuoteRequest) -> QuoteOut:
        """Everything the compose screen shows before sending. No side effects."""
        async with self._db.transaction() as session:
            repository = SmsRepository(session)
            recipient = await self._resolve(repository, user, request)
            evaluation = await self._evaluate(repository, user, recipient, request.body)
        return self._quote_out(recipient, evaluation)

    # -- consent ---------------------------------------------------------------------------

    async def set_consent(
        self, user: AuthenticatedUser, request: ConsentRequest, ip: str | None
    ) -> ConsentOut:
        """Record the sender's attestation (or its withdrawal) for one recipient. A recipient
        replying is not consent."""
        version = self._settings.sms_attestation_version
        async with self._db.transaction() as session:
            repository = SmsRepository(session)
            recipient = await self._resolve(repository, user, request)
            e164 = recipient.destination.e164
            current = await repository.has_consent(user.id, e164)
            if current != (request.decision == "granted"):
                await repository.record_consent(
                    user_id=user.id,
                    recipient=e164,
                    decision=request.decision,
                    notice_version=version,
                    ip_prefix=ip_prefix(ip),
                )
                await self._audit.record(
                    session,
                    category="consent",
                    action=f"sms.consent_{request.decision}",
                    actor_id=user.id,
                    actor_role=user.role,
                    target_type="sms_recipient",
                    target_id=mask_phone(e164),
                    ip=ip,
                    metadata={"notice_version": version},
                )
            granted = await repository.has_consent(user.id, e164)
            capability = await repository.capability(recipient.destination.country_code)
        return ConsentOut(
            required=capability.consent_required if capability else True,
            granted=granted,
            notice_version=version,
        )

    # -- sending ---------------------------------------------------------------------------

    async def send(
        self, user: AuthenticatedUser, request: SendSmsRequest, key: UUID, ip: str | None
    ) -> tuple[SmsMessageOut, bool]:
        """Store a message once. Returns (message, created). Repeating the key with the same
        content returns the original and sends nothing; with different content it is a 409."""
        return await self._send(user, request, request.body, key, ip)

    async def retry(
        self, user: AuthenticatedUser, message_id: UUID, key: UUID, ip: str | None
    ) -> tuple[SmsMessageOut, bool]:
        """User-initiated resend of a failed message: new message, new key, all checks again."""
        async with self._db.transaction() as session:
            row = await SmsRepository(session).message_for_user(user.id, message_id)
        if row is None or row["direction"] != "outbound":
            raise NotFoundError("Message not found.")
        if row["status"] not in ("failed", "undelivered") or not row["body"]:
            raise ConflictError("Only failed messages can be sent again.", code="not_retryable")
        fields = RecipientFields(conversation_id=row["conversation_id"])
        return await self._send(user, fields, row["body"], key, ip)

    async def _send(
        self,
        user: AuthenticatedUser,
        fields: RecipientFields,
        body: str,
        key: UUID,
        ip: str | None,
    ) -> tuple[SmsMessageOut, bool]:
        async with self._db.transaction() as session:
            repository = SmsRepository(session)
            recipient = await self._resolve(repository, user, fields)
            digest = request_hash(recipient.destination, body)
            existing = await repository.find_by_key(user.id, key)
            if existing is not None:
                return await self._duplicate(repository, user, existing, digest), False
            hourly = await repository.setting("sms_user_limit_per_hour")
            per_recipient = await repository.setting("sms_recipient_limit_per_hour")

        # Counted in their own committed transactions, so refused attempts still count.
        await self._limiter.hit(
            Limit(
                "sms.send.user.hour",
                int(hourly) if isinstance(hourly, int) else 30,
                3600,
                message="You've reached your hourly SMS limit. Please try again later.",
            ),
            str(user.id),
        )
        await self._limiter.hit(SMS_SEND_PER_USER_DAY, str(user.id))
        if ip:
            await self._limiter.hit(SMS_SEND_PER_IP, ip)
        await self._limiter.hit(
            Limit(
                "sms.send.recipient.hour",
                int(per_recipient) if isinstance(per_recipient, int) else 10,
                3600,
                message="This number has received too many messages recently. Please wait.",
            ),
            recipient.destination.e164,
        )

        denied: Blocker | None = None
        out: SmsMessageOut | None = None
        try:
            async with self._db.transaction() as session:
                repository = SmsRepository(session)
                evaluation = await self._evaluate(repository, user, recipient, body)
                if evaluation.blockers:
                    # Nothing has been written yet. The denial is audited after this
                    # transaction ends, on its own connection.
                    denied = evaluation.blockers[0]
                else:
                    message_id = await self._store(
                        session, repository, user, recipient, evaluation, body, key, digest, ip
                    )
                    rows = await repository.messages_by_ids([message_id])
                    out = render_message(rows[0], user.id, self._clock())
        except IntegrityError as exc:
            if "uq_messages_sender_idempotency" not in str(exc):
                raise
            # A concurrent request with the same key won the race: return its message.
            async with self._db.transaction() as session:
                repository = SmsRepository(session)
                existing = await repository.find_by_key(user.id, key)
                if existing is None:  # pragma: no cover
                    raise
                return await self._duplicate(repository, user, existing, digest), False

        if denied is not None:
            await self._audit_denial(user, recipient, denied, ip)
            raise _raise(denied)
        if out is None:  # pragma: no cover - set whenever nothing was denied
            raise ServiceUnavailableError("SMS is unavailable right now.")
        self._hub.publish(
            [user.id],
            event(
                "sms.message.created",
                {"message": out.model_dump(mode="json")},
                conversation_id=out.conversation_id,
            ),
        )
        self._wake()
        return out, True

    async def _duplicate(
        self,
        repository: SmsRepository,
        user: AuthenticatedUser,
        existing: dict[str, Any],
        digest: str,
    ) -> SmsMessageOut:
        if existing["request_hash"] != digest:
            raise ConflictError(
                "This idempotency key was already used for a different message.",
                code="idempotency_conflict",
            )
        rows = await repository.messages_by_ids([existing["id"]])
        return render_message(rows[0], user.id, self._clock())

    async def _audit_denial(
        self, user: AuthenticatedUser, recipient: Recipient, blocker: Blocker, ip: str | None
    ) -> None:
        await self._audit.record_standalone(
            category="sms",
            action="sms.send_denied",
            outcome="denied",
            actor_id=user.id,
            actor_role=user.role,
            target_type="sms_recipient",
            target_id=mask_phone(recipient.destination.e164),
            ip=ip,
            metadata={"reason": blocker.code, "mode": self._provider.mode},
        )

    async def _store(
        self,
        session: Any,
        repository: SmsRepository,
        user: AuthenticatedUser,
        recipient: Recipient,
        evaluation: Evaluation,
        body: str,
        key: UUID,
        digest: str,
        ip: str | None,
    ) -> UUID:
        destination = recipient.destination
        conversation_id = await repository.get_or_create_conversation(user.id, destination.e164)
        await self._ensure_sender(repository, user.id, conversation_id, evaluation, destination)
        segment = evaluation.segment
        message_id = await repository.insert_outbound_message(
            conversation_id=conversation_id,
            user_id=user.id,
            body=body,
            encoding=segment.encoding,
            char_count=segment.characters,
            segment_count=segment.segments,
            key=key,
            request_hash=digest,
            is_simulated=self._provider.is_simulated,
            capability_id=evaluation.capability.id if evaluation.capability else None,
            credit_cost_units=(
                evaluation.cost_units
                if self._provider.is_simulated and evaluation.cost_units
                else None
            ),
        )
        delivery_id = await repository.insert_first_delivery(
            message_id=message_id,
            provider_configuration_id=evaluation.cfg.id,
            recipient_phone=destination.e164,
            is_simulated=self._provider.is_simulated,
            next_attempt_at=self._clock(),
        )
        # Hold the estimated demo cost. A shortfall that appeared since the check refuses the
        # send and rolls the whole message back.
        await credit_ledger.reserve(session, message_id, provider=self._provider.name)
        await repository.unarchive(conversation_id, user.id)
        await self._audit.record(
            session,
            category="sms",
            action="sms.queued",
            actor_id=user.id,
            actor_role=user.role,
            target_type="message",
            target_id=str(message_id),
            ip=ip,
            metadata={
                "delivery_id": str(delivery_id),
                "provider": self._provider.name,
                "mode": self._provider.mode,
                "recipient": mask_phone(destination.e164),
                "country": destination.country_code,
                "segments": segment.segments,
                "attempt": 1,
            },
        )
        return message_id

    async def _ensure_sender(
        self,
        repository: SmsRepository,
        user_id: UUID,
        conversation_id: UUID,
        evaluation: Evaluation,
        destination: Destination,
    ) -> None:
        """Reply routing (OD-011): a platform number is held by one user per remote number for
        the route TTL, so a reply can only ever belong to one conversation. A registered
        alphanumeric sender cannot receive replies, so it needs no route."""
        capability = evaluation.capability
        remote = destination.e164
        sender_id = capability.provider_settings.get("sender_id") if capability else None
        if (
            capability is not None
            and capability.alphanumeric_sender_allowed
            and isinstance(sender_id, str)
            and sender_id
            and evaluation.verdict.replies == "unsupported"
        ):
            return
        ttl = await repository.setting("sms_route_ttl_days")
        days = int(ttl) if isinstance(ttl, int) and ttl > 0 else 30
        await repository.release_expired_routes(remote)
        if await repository.route_platform_number(user_id, remote):
            await repository.refresh_route(user_id, remote, days)
            return
        for _ in range(2):
            used = await repository.numbers_in_use(remote)
            for number in evaluation.cfg.sender_numbers:
                if number in used:
                    continue
                if await repository.create_route(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    platform=number,
                    remote=remote,
                    ttl_days=days,
                ):
                    return
        raise ServiceUnavailableError(
            "No sender number is free for this recipient right now. Please try again later.",
            code="sender_capacity",
        )

    # -- reading ---------------------------------------------------------------------------

    async def list_conversations(
        self, user: AuthenticatedUser, *, archived: bool, page: int, page_size: int
    ) -> tuple[list[SmsConversationOut], int]:
        async with self._db.transaction() as session:
            repository = SmsRepository(session)
            rows, total = await repository.conversations(
                user.id, archived=archived, offset=(page - 1) * page_size, limit=page_size
            )
            contacts = await repository.contacts_by_phone(
                user.id, [r["remote_phone"] for r in rows]
            )
            capabilities = {c.country_code: c for c in await repository.capabilities()}
        items: list[SmsConversationOut] = []
        for row in rows:
            phone = row["remote_phone"]
            region = region_of(phone)
            contact = contacts.get(phone)
            capability = capabilities.get(region or "")
            replies = evaluate(capability, number_type="mobile", live=self._live).replies
            items.append(
                SmsConversationOut(
                    id=row["id"],
                    masked_phone=mask_phone(phone),
                    country_code=region,
                    display_name=contact[1] if contact else None,
                    contact_id=contact[0] if contact else None,
                    last_message_preview=preview(row["last_body"]),
                    last_message_direction=row["last_direction"],
                    last_message_status=row["last_status"],
                    last_message_at=row["last_message_at"],
                    last_is_simulated=bool(row["last_is_simulated"]),
                    unread_count=int(row["unread_count"]),
                    is_archived=row["is_archived"],
                    is_muted=bool(row["is_muted"]),
                    replies=replies,
                )
            )
        return items, total

    async def list_messages(
        self, user: AuthenticatedUser, conversation_id: UUID, *, before_seq: int | None, limit: int
    ) -> SmsMessagePage:
        async with self._db.transaction() as session:
            repository = SmsRepository(session)
            if await repository.conversation_remote(user.id, conversation_id) is None:
                raise NotFoundError(_NOT_FOUND)
            rows, more = await repository.messages_page(
                user.id, conversation_id, before_seq=before_seq, limit=limit
            )
            last_read = await repository.last_read_seq(user.id, conversation_id)
        now = self._clock()
        return SmsMessagePage(
            messages=[render_message(r, user.id, now) for r in rows],
            has_more_before=more,
            last_read_seq=last_read,
        )

    async def get_message(self, user: AuthenticatedUser, message_id: UUID) -> SmsMessageDetail:
        async with self._db.transaction() as session:
            repository = SmsRepository(session)
            row = await repository.message_for_user(user.id, message_id)
            if row is None:
                raise NotFoundError("Message not found.")
            events = await repository.message_events(message_id)
        return SmsMessageDetail(
            message=render_message(row, user.id, self._clock()),
            events=[DeliveryEventOut(**e) for e in events],
        )

    async def mark_read(
        self, user: AuthenticatedUser, conversation_id: UUID, up_to_seq: int
    ) -> SmsReadState:
        async with self._db.transaction() as session:
            repository = SmsRepository(session)
            if await repository.conversation_remote(user.id, conversation_id) is None:
                raise NotFoundError(_NOT_FOUND)
            last_read = await repository.advance_read(user.id, conversation_id, up_to_seq)
            unread = await repository.unread_count(user.id, conversation_id)
        state = SmsReadState(
            conversation_id=conversation_id, last_read_seq=last_read, unread_count=unread
        )
        self._hub.publish(
            [user.id],
            event("sms.conversation.read", state.model_dump(mode="json"), conversation_id),
        )
        return state
