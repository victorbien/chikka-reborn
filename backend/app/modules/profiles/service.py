"""Profile reads and edits (FR-AUTH-007, FR-AUTH-011, FR-AUTH-013, FR-AUTH-015).

Profile data lives in public.profiles; credentials stay in Supabase Auth. Every method takes
the authenticated caller and only ever touches that caller's own row (CC-04).
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    UnprocessableError,
)
from app.core.privacy import mask_phone
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.integrations.storage_provider import StorageError, StorageProvider
from app.modules.audit.service import AuditLogger
from app.modules.auth.repositories import PhoneRepository
from app.modules.profiles.avatar import InvalidImageError, process_avatar
from app.modules.profiles.models import Profile
from app.modules.profiles.presence import PresenceRegistry
from app.modules.profiles.reference import RESERVED_USERNAMES
from app.modules.profiles.repository import ProfileRepository, UsernameTakenError
from app.modules.profiles.schemas import (
    OnboardingRequest,
    PhoneSummary,
    PresencePreference,
    PresenceResponse,
    PrivacySettings,
    PrivacySettingsUpdate,
    ProfileResponse,
    ProfileUpdateRequest,
)
from app.modules.rate_limits import service as limits
from app.modules.rate_limits.service import RateLimiter

logger = logging.getLogger(__name__)

AVATAR_URL_TTL_SECONDS = 3600


class ProfileService:
    def __init__(
        self,
        *,
        database: Database,
        storage: StorageProvider,
        limiter: RateLimiter,
        audit: AuditLogger,
        presence: PresenceRegistry,
    ) -> None:
        self._db = database
        self._storage = storage
        self._limiter = limiter
        self._audit = audit
        self._presence = presence

    # -- reads ---------------------------------------------------------------------------

    async def get_me(self, user: AuthenticatedUser) -> ProfileResponse:
        async with self._db.transaction() as session:
            profile = await self._own_profile(ProfileRepository(session), user)
            phone = await PhoneRepository(session).any_verified_for_user(user.id)
        return await self._to_response(profile, user, phone_row=phone)

    async def _own_profile(self, repository: ProfileRepository, user: AuthenticatedUser) -> Profile:
        profile = await repository.get(user.id)
        if profile is None or profile.status == "deleted":
            raise NotFoundError("Profile not found.")
        return profile

    async def _avatar_url(self, path: str | None) -> str | None:
        if not path:
            return None
        try:
            return await self._storage.signed_url(path, AVATAR_URL_TTL_SECONDS)
        except StorageError:
            # The UI falls back to initials; the rest of the profile still loads.
            return None

    async def _to_response(
        self, profile: Profile, user: AuthenticatedUser, *, phone_row: Any = None
    ) -> ProfileResponse:
        phone = (
            PhoneSummary(
                masked=mask_phone(phone_row.e164),
                verification_mode=phone_row.verification_mode,
                verified_at=phone_row.verified_at,
            )
            if phone_row is not None and phone_row.verified_at is not None
            else None
        )
        return ProfileResponse(
            id=profile.id,
            username=profile.username,
            display_name=profile.display_name,
            email=user.email,
            email_verified=profile.status != "pending_verification",
            avatar_url=await self._avatar_url(profile.avatar_path),
            bio=profile.bio,
            status_message=profile.status_message,
            country_code=profile.country_code,
            language=profile.language,
            time_zone=profile.time_zone,
            theme=profile.theme,
            ui_mode=profile.ui_mode,
            presence_preference=profile.presence_preference,
            role="admin" if profile.role == "admin" else "user",
            status=profile.status,
            onboarding_completed=profile.onboarding_completed_at is not None,
            phone=phone,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    # -- writes --------------------------------------------------------------------------

    async def update_me(
        self, user: AuthenticatedUser, request: ProfileUpdateRequest
    ) -> ProfileResponse:
        changes = request.model_dump(exclude_unset=True)
        # Fields that may not be cleared once set.
        for required in ("display_name", "language", "time_zone", "theme", "ui_mode"):
            if required in changes and changes[required] is None:
                raise UnprocessableError(
                    f"{required.replace('_', ' ').capitalize()} cannot be empty.",
                    details={"problems": [{"field": f"body.{required}", "reason": "Required"}]},
                )
        await self._limiter.hit(limits.PROFILE_WRITE_PER_USER, str(user.id))
        async with self._db.transaction() as session:
            repository = ProfileRepository(session)
            profile = await self._own_profile(repository, user)
            if changes:
                profile = await repository.apply(profile, changes)
            phone = await PhoneRepository(session).any_verified_for_user(user.id)
        return await self._to_response(profile, user, phone_row=phone)

    async def get_privacy(self, user: AuthenticatedUser) -> PrivacySettings:
        async with self._db.transaction() as session:
            profile = await self._own_profile(ProfileRepository(session), user)
        return self._privacy(profile)

    async def update_privacy(
        self, user: AuthenticatedUser, request: PrivacySettingsUpdate
    ) -> PrivacySettings:
        changes = request.model_dump(exclude_unset=True)
        await self._limiter.hit(limits.PROFILE_WRITE_PER_USER, str(user.id))
        async with self._db.transaction() as session:
            repository = ProfileRepository(session)
            profile = await self._own_profile(repository, user)
            if changes:
                profile = await repository.apply(profile, changes)
                await self._audit.record(
                    session,
                    category="privacy",
                    action="privacy.settings_changed",
                    actor_id=user.id,
                    metadata={"fields": sorted(changes)},
                )
        return self._privacy(profile)

    @staticmethod
    def _privacy(profile: Profile) -> PrivacySettings:
        return PrivacySettings(
            profile_visibility=profile.profile_visibility,
            share_presence=profile.share_presence,
            show_last_seen=profile.show_last_seen,
            discoverable_by_email=profile.discoverable_by_email,
            discoverable_by_phone=profile.discoverable_by_phone,
        )

    async def complete_onboarding(
        self, user: AuthenticatedUser, request: OnboardingRequest
    ) -> ProfileResponse:
        await self._limiter.hit(limits.PROFILE_WRITE_PER_USER, str(user.id))
        try:
            async with self._db.transaction() as session:
                repository = ProfileRepository(session)
                profile = await self._own_profile(repository, user)
                if profile.onboarding_completed_at is not None:
                    raise ConflictError("Your profile is already set up.", code="already_onboarded")
                changes: dict[str, Any] = request.model_dump()
                changes["onboarding_completed_at"] = datetime.now(UTC)
                profile = await repository.apply(profile, changes)
                await self._audit.record(
                    session, category="auth", action="profile.onboarded", actor_id=user.id
                )
        except UsernameTakenError as exc:
            # The failed transaction is gone; look up alternatives in a fresh one.
            async with self._db.transaction() as session:
                suggestions = await self._suggest_usernames(
                    ProfileRepository(session), request.username
                )
            raise ConflictError(
                "That username is taken.",
                code="username_taken",
                details={"suggestions": suggestions},
            ) from exc
        return await self._to_response(profile, user)

    @staticmethod
    async def _suggest_usernames(repository: ProfileRepository, base: str) -> list[str]:
        stem = base[:16]
        suggestions: list[str] = []
        for _ in range(8):
            candidate = f"{stem}{secrets.randbelow(10_000)}"
            if candidate.lower() in RESERVED_USERNAMES:
                continue
            if not await repository.username_taken(candidate):
                suggestions.append(candidate)
            if len(suggestions) == 3:
                break
        return suggestions

    async def upload_avatar(self, user: AuthenticatedUser, data: bytes) -> str | None:
        await self._limiter.hit(limits.PROFILE_WRITE_PER_USER, str(user.id))
        try:
            encoded = await run_in_threadpool(process_avatar, data)
        except InvalidImageError as exc:
            raise UnprocessableError(
                exc.reason,
                code="invalid_image",
                details={"problems": [{"field": "avatar", "reason": exc.reason}]},
            ) from exc

        path = f"{user.id}/{uuid.uuid4().hex}.webp"
        try:
            await self._storage.upload(path, encoded, "image/webp")
        except StorageError as exc:
            raise ServiceUnavailableError(
                "Photo upload is unavailable right now. Your current photo is unchanged.",
                code="storage_unavailable",
            ) from exc

        async with self._db.transaction() as session:
            repository = ProfileRepository(session)
            profile = await self._own_profile(repository, user)
            previous = profile.avatar_path
            await repository.apply(profile, {"avatar_path": path})
        await self._delete_quietly(previous)
        return await self._avatar_url(path)

    async def remove_avatar(self, user: AuthenticatedUser) -> None:
        async with self._db.transaction() as session:
            repository = ProfileRepository(session)
            profile = await self._own_profile(repository, user)
            previous = profile.avatar_path
            if previous is not None:
                await repository.apply(profile, {"avatar_path": None})
        await self._delete_quietly(previous)

    async def _delete_quietly(self, path: str | None) -> None:
        if not path:
            return
        try:
            await self._storage.delete(path)
        except StorageError:
            logger.warning("old avatar not deleted; it is unreferenced and private")

    # -- presence ------------------------------------------------------------------------

    async def set_presence(
        self, user: AuthenticatedUser, preference: PresencePreference
    ) -> PresenceResponse:
        async with self._db.transaction() as session:
            repository = ProfileRepository(session)
            profile = await self._own_profile(repository, user)
            profile = await repository.apply(profile, {"presence_preference": preference})
        self._presence.heartbeat(str(user.id), idle=False)
        return PresenceResponse(
            status=self._presence.status(str(user.id), preference),
            preference=preference,
            last_seen_at=profile.last_seen_at,
        )

    async def heartbeat(self, user: AuthenticatedUser, *, idle: bool) -> PresenceResponse:
        if user.status != "active":
            raise PermissionDeniedError("Confirm your email first.", code="email_not_verified")
        persist = self._presence.heartbeat(str(user.id), idle=idle)
        async with self._db.transaction() as session:
            repository = ProfileRepository(session)
            if persist:
                await repository.touch_last_seen(user.id, datetime.now(UTC))
            profile = await self._own_profile(repository, user)
        preference: PresencePreference = profile.presence_preference  # type: ignore[assignment]
        return PresenceResponse(
            status=self._presence.status(str(user.id), preference),
            preference=preference,
            last_seen_at=profile.last_seen_at,
        )
