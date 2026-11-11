"""Who is calling (every protected request) and account deletion (FR-AUTH-009)."""

import logging
from datetime import UTC, datetime

from app.core.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    ServiceUnavailableError,
)
from app.core.security import AuthenticatedUser, TokenClaims
from app.database.session import Database
from app.integrations.auth_provider import AuthProvider, AuthUnavailableError
from app.integrations.otp_delivery import SimulatedInbox
from app.integrations.storage_provider import StorageError, StorageProvider
from app.modules.audit.service import AuditLogger
from app.modules.auth.repositories import AuthSessionRepository, PhoneRepository
from app.modules.auth.service import UNAVAILABLE_STATUSES, AuthService, RequestMeta
from app.modules.profiles.presence import PresenceRegistry
from app.modules.profiles.repository import ProfileRepository

logger = logging.getLogger(__name__)

DELETED_DISPLAY_NAME = "Deleted user"


class AccountResolver:
    """Turns verified token claims into the caller, checking the database each time.

    * The profile must exist and not be suspended or deleted.
    * The Supabase Auth session must still exist, so logout and revocation take effect at
      once rather than when the access token expires (FR-AUTH-010 AC2, FR-AUTH-014 AC1).
    """

    def __init__(self, database: Database) -> None:
        self._db = database

    async def resolve(self, claims: TokenClaims) -> AuthenticatedUser:
        async with self._db.transaction() as session:
            if not await AuthSessionRepository(session).is_active(
                claims.session_id, claims.user_id
            ):
                raise AuthenticationError(
                    "Your session has ended. Please sign in again.", code="session_revoked"
                )
            profile = await ProfileRepository(session).get(claims.user_id)
        if profile is None:
            raise AuthenticationError("Please sign in.")
        if profile.status in UNAVAILABLE_STATUSES:
            raise PermissionDeniedError(
                "This account is not available.", code="account_unavailable"
            )
        return AuthenticatedUser(
            id=profile.id,
            session_id=claims.session_id,
            email=claims.email,
            role="admin" if profile.role == "admin" else "user",
            status=profile.status,
            onboarded=profile.onboarding_completed_at is not None,
        )


class AccountService:
    def __init__(
        self,
        *,
        database: Database,
        provider: AuthProvider,
        storage: StorageProvider,
        auth_service: AuthService,
        audit: AuditLogger,
        presence: PresenceRegistry,
        inbox: SimulatedInbox,
    ) -> None:
        self._db = database
        self._provider = provider
        self._storage = storage
        self._auth = auth_service
        self._audit = audit
        self._presence = presence
        self._inbox = inbox

    async def delete_account(
        self, user: AuthenticatedUser, password: str, meta: RequestMeta
    ) -> datetime:
        """Re-authenticate, then erase personal profile data and disable sign-in.

        Kept (FR-AUTH-009 AC3/AC4): the profile row itself (status=deleted, so messages show
        "Deleted user"), consent history, credit ledger and audit rows. Removed: username,
        display name, bio, photo, country, phone numbers, sessions; the auth email is replaced.
        """
        await self._auth.reauthenticate(user, password, meta)
        now = datetime.now(UTC)
        old_avatar: str | None = None

        async with self._db.transaction() as session:
            profiles = ProfileRepository(session)
            profile = await profiles.get_for_update(user.id)
            if profile is None or profile.status == "deleted":
                raise PermissionDeniedError(
                    "This account is not available.", code="account_unavailable"
                )
            old_avatar = profile.avatar_path
            await profiles.apply(
                profile,
                {
                    "status": "deleted",
                    "deleted_at": now,
                    "deletion_requested_at": now,
                    "username": None,
                    "onboarding_completed_at": None,
                    "display_name": DELETED_DISPLAY_NAME,
                    "bio": None,
                    "avatar_path": None,
                    "country_code": None,
                    "last_seen_at": None,
                },
            )
            await PhoneRepository(session).release_all(user.id, now)
            await AuthSessionRepository(session).delete_all_except(user.id, keep=None)
            await self._audit.record(
                session,
                category="privacy",
                action="account.deleted",
                actor_id=user.id,
                target_type="profile",
                target_id=str(user.id),
                ip=meta.ip,
            )
            # Last step inside the transaction: if Supabase Auth cannot disable the login,
            # nothing above is committed and the user can retry.
            try:
                await self._provider.disable_user(str(user.id))
            except AuthUnavailableError as exc:
                raise ServiceUnavailableError(
                    "Account deletion is temporarily unavailable. Nothing was changed.",
                    code="deletion_unavailable",
                ) from exc

        self._presence.clear(str(user.id))
        self._inbox.clear(str(user.id))
        if old_avatar:
            try:
                await self._storage.delete(old_avatar)
            except StorageError:
                # The object is unreachable (private bucket, path no longer referenced);
                # flag it for the scheduled purge rather than failing the deletion.
                logger.error("avatar purge pending after account deletion")
        return now
