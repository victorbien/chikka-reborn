"""Authentication flows (FR-AUTH-001/002/004/005/006/010/014).

Supabase Auth owns credentials. This service adds what the platform requires on top: rate
limits and lockout, neutral responses that do not reveal whether an email is registered,
profile state checks, consent records and audit events.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    UnprocessableError,
)
from app.core.privacy import ip_prefix
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.integrations.auth_provider import (
    AuthProvider,
    AuthSession,
    AuthUnavailableError,
    EmailNotConfirmedError,
    InvalidCredentialsError,
    InvalidTokenError,
    SignOutScope,
    WeakPasswordError,
)
from app.modules.audit.service import AuditLogger
from app.modules.auth.repositories import AuthSessionRepository, ConsentRepository
from app.modules.auth.schemas import SessionInfo
from app.modules.notifications.service import create_notification
from app.modules.profiles.presence import PresenceRegistry
from app.modules.profiles.repository import ProfileRepository
from app.modules.rate_limits import service as limits
from app.modules.rate_limits.service import RateLimiter

logger = logging.getLogger(__name__)

UNAVAILABLE_STATUSES = frozenset({"suspended", "deleted"})

NEUTRAL_REGISTER = "Check your inbox. If the address can be used, we sent a link to confirm it."
NEUTRAL_RESET = "If an account exists for that address, we sent a password reset link."
NEUTRAL_RESEND = "If the address needs confirming, we sent a new link."


@dataclass(frozen=True)
class RequestMeta:
    ip: str | None
    user_agent: str | None = None


def _unavailable(
    message: str = "Sign-in is temporarily unavailable. Please try again.",
) -> ServiceUnavailableError:
    return ServiceUnavailableError(message, code="auth_unavailable")


class AuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        provider: AuthProvider,
        limiter: RateLimiter,
        audit: AuditLogger,
        presence: PresenceRegistry,
    ) -> None:
        self._settings = settings
        self._db = database
        self._provider = provider
        self._limiter = limiter
        self._audit = audit
        self._presence = presence

    def _link(self, path: str) -> str:
        return self._settings.frontend_base_url.rstrip("/") + path

    # -- registration and verification ---------------------------------------------------

    async def register(
        self, *, email: str, password: str, display_name: str, meta: RequestMeta
    ) -> str:
        await self._limiter.hit(limits.REGISTER_PER_IP, meta.ip or "unknown")
        try:
            user_id = await self._provider.sign_up(
                email=email,
                password=password,
                display_name=display_name,
                redirect_to=self._link("/auth/verify-email"),
            )
        except WeakPasswordError as exc:
            raise UnprocessableError(
                "Choose a stronger password.",
                code="weak_password",
                details={
                    "problems": [{"field": "body.password", "reason": "Password is too weak"}]
                },
            ) from exc
        except AuthUnavailableError as exc:
            raise _unavailable("Registration is temporarily unavailable.") from exc

        # For an address that is already registered the provider returns a throwaway id with
        # no profile behind it. Answer identically (FR-AUTH-001 AC3).
        async with self._db.transaction() as session:
            try:
                uid = UUID(user_id)
            except ValueError:
                return NEUTRAL_REGISTER
            if await ProfileRepository(session).exists(uid):
                consents = ConsentRepository(session)
                for consent_type, version in (
                    ("terms", self._settings.terms_version),
                    ("privacy", self._settings.privacy_version),
                ):
                    await consents.grant(
                        user_id=uid,
                        consent_type=consent_type,
                        notice_version=version,
                        source="registration",
                        ip_prefix=ip_prefix(meta.ip),
                    )
                await self._audit.record(
                    session, category="auth", action="auth.register", actor_id=uid, ip=meta.ip
                )
        return NEUTRAL_REGISTER

    async def verify_email(self, token_hash: str, meta: RequestMeta) -> AuthSession:
        await self._limiter.hit(limits.VERIFY_EMAIL_PER_IP, meta.ip or "unknown")
        try:
            auth_session = await self._provider.verify_token_hash(token_hash, "signup")
        except InvalidTokenError as exc:
            raise BadRequestError(
                "This confirmation link is invalid or has expired. Request a new one.",
                code="invalid_or_expired_link",
            ) from exc
        except AuthUnavailableError as exc:
            raise _unavailable() from exc
        await self._finish_sign_in(auth_session, meta, action="auth.email_verified")
        return auth_session

    async def resend_verification(self, email: str, meta: RequestMeta) -> str:
        await self._limiter.hit(limits.RESEND_PER_IP, meta.ip or "unknown")
        await self._limiter.hit(limits.RESEND_PER_EMAIL, email)
        try:
            await self._provider.resend_signup(
                email=email, redirect_to=self._link("/auth/verify-email")
            )
        except AuthUnavailableError as exc:
            raise _unavailable() from exc
        return NEUTRAL_RESEND

    # -- sign-in -------------------------------------------------------------------------

    async def login(self, *, email: str, password: str, meta: RequestMeta) -> AuthSession:
        email = email.strip().lower()
        ip = meta.ip or "unknown"
        await self._limiter.ensure_not_locked(limits.LOGIN_PER_ACCOUNT, email)
        await self._limiter.ensure_not_locked(limits.LOGIN_PER_IP, ip)
        try:
            auth_session = await self._provider.sign_in(email=email, password=password)
        except InvalidCredentialsError as exc:
            locked = await self._limiter.record_failure(limits.LOGIN_PER_ACCOUNT, email)
            await self._limiter.record_failure(limits.LOGIN_PER_IP, ip)
            await self._audit.record_standalone(
                category="auth",
                action="auth.lockout" if locked else "auth.login",
                outcome="denied",
                ip=meta.ip,
                metadata={"reason": "invalid_credentials"},
            )
            raise AuthenticationError(
                "Email or password is incorrect.", code="invalid_credentials"
            ) from exc
        except EmailNotConfirmedError as exc:
            # Only reachable with the correct password, so it reveals nothing new.
            raise PermissionDeniedError(
                "Confirm your email address before signing in.", code="email_not_verified"
            ) from exc
        except AuthUnavailableError as exc:
            raise _unavailable() from exc

        await self._finish_sign_in(auth_session, meta, action="auth.login")
        await self._limiter.reset(limits.LOGIN_PER_ACCOUNT, email)
        return auth_session

    async def _finish_sign_in(
        self, auth_session: AuthSession, meta: RequestMeta, *, action: str
    ) -> None:
        """Reject unavailable accounts, activate verified ones, and audit the sign-in."""
        user_id = UUID(auth_session.user_id)
        available = False
        async with self._db.transaction() as session:
            profiles = ProfileRepository(session)
            profile = await profiles.get(user_id)
            if profile is not None and profile.status not in UNAVAILABLE_STATUSES:
                available = True
                await profiles.activate_if_pending(user_id)
                await self._audit.record(
                    session, category="auth", action=action, actor_id=user_id, ip=meta.ip
                )
        if not available:
            # After the transaction, so no connection is held during the network call.
            await self._revoke_quietly(auth_session.access_token, "local")
            raise PermissionDeniedError(
                "This account is not available.", code="account_unavailable"
            )

    async def refresh(self, refresh_token: str | None, meta: RequestMeta) -> AuthSession:
        if not refresh_token:
            raise AuthenticationError("Please sign in.", code="not_authenticated")
        await self._limiter.hit(limits.REFRESH_PER_IP, meta.ip or "unknown")
        try:
            auth_session = await self._provider.refresh(refresh_token)
        except InvalidTokenError as exc:
            raise AuthenticationError("Your session has ended. Please sign in again.") from exc
        except AuthUnavailableError as exc:
            raise _unavailable() from exc
        async with self._db.transaction() as session:
            profile = await ProfileRepository(session).get(UUID(auth_session.user_id))
        if profile is None or profile.status in UNAVAILABLE_STATUSES:
            await self._revoke_quietly(auth_session.access_token, "local")
            raise PermissionDeniedError(
                "This account is not available.", code="account_unavailable"
            )
        return auth_session

    async def logout(
        self, user: AuthenticatedUser, access_token: str, scope: str, meta: RequestMeta
    ) -> None:
        """Always completes locally. Provider failure falls back to deleting the session rows."""
        self._presence.clear(str(user.id))
        provider_scope: SignOutScope = "global" if scope == "global" else "local"
        try:
            await self._provider.sign_out(access_token, provider_scope)
        except InvalidTokenError:
            pass
        except AuthUnavailableError:
            logger.warning("provider sign-out failed; revoking sessions directly")
        async with self._db.transaction() as session:
            sessions = AuthSessionRepository(session)
            if provider_scope == "global":
                await sessions.delete_all_except(user.id, keep=None)
            else:
                await sessions.delete(user.session_id, user.id)
            await self._audit.record(
                session,
                category="auth",
                action="auth.logout",
                actor_id=user.id,
                ip=meta.ip,
                metadata={"scope": provider_scope},
            )

    async def _revoke_quietly(self, access_token: str, scope: str) -> None:
        try:
            await self._provider.sign_out(access_token, "global" if scope == "global" else "local")
        except (InvalidTokenError, AuthUnavailableError):
            logger.warning("could not revoke session for unavailable account")

    # -- password reset ------------------------------------------------------------------

    async def request_password_reset(self, email: str, meta: RequestMeta) -> str:
        await self._limiter.hit(limits.RESET_PER_IP, meta.ip or "unknown")
        await self._limiter.hit(limits.RESET_PER_EMAIL, email)
        try:
            await self._provider.request_recovery(
                email=email, redirect_to=self._link("/auth/reset-password")
            )
        except AuthUnavailableError as exc:
            raise _unavailable() from exc
        await self._audit.record_standalone(
            category="auth", action="auth.password_reset_requested", ip=meta.ip
        )
        return NEUTRAL_RESET

    async def confirm_password_reset(
        self, token_hash: str, new_password: str, meta: RequestMeta
    ) -> None:
        await self._limiter.hit(limits.RESET_CONFIRM_PER_IP, meta.ip or "unknown")
        try:
            auth_session = await self._provider.verify_token_hash(token_hash, "recovery")
        except InvalidTokenError as exc:
            raise BadRequestError(
                "This reset link is invalid, expired or already used. Request a new one.",
                code="invalid_or_expired_link",
            ) from exc
        except AuthUnavailableError as exc:
            raise _unavailable() from exc

        try:
            await self._provider.update_password(auth_session.access_token, new_password)
        except WeakPasswordError as exc:
            await self._revoke_quietly(auth_session.access_token, "global")
            raise UnprocessableError(
                "Choose a different, stronger password, then request a new reset link.",
                code="weak_password",
            ) from exc
        except (InvalidTokenError, AuthUnavailableError) as exc:
            raise _unavailable() from exc

        # Every session ends, including the one the link created (FR-AUTH-005 AC3).
        await self._revoke_quietly(auth_session.access_token, "global")
        user_id = UUID(auth_session.user_id)
        async with self._db.transaction() as session:
            await AuthSessionRepository(session).delete_all_except(user_id, keep=None)
            await ProfileRepository(session).activate_if_pending(user_id)
            await self._audit.record(
                session,
                category="auth",
                action="auth.password_reset",
                actor_id=user_id,
                ip=meta.ip,
            )
            await create_notification(
                session,
                user_id=user_id,
                notification_type="security",
                title="Your password was reset",
                body="All your devices were signed out. If this wasn't you, reset it again now.",
            )

    # -- re-authentication ---------------------------------------------------------------

    async def reauthenticate(
        self, user: AuthenticatedUser, password: str, meta: RequestMeta
    ) -> None:
        """Confirm the password before a sensitive change (deletion, phone change)."""
        subject = str(user.id)
        await self._limiter.ensure_not_locked(limits.REAUTH_PER_USER, subject)
        if not user.email:
            raise PermissionDeniedError(
                "Your password could not be confirmed.", code="reauthentication_failed"
            )
        try:
            check = await self._provider.sign_in(email=user.email, password=password)
        except (InvalidCredentialsError, EmailNotConfirmedError) as exc:
            await self._limiter.record_failure(limits.REAUTH_PER_USER, subject)
            await self._audit.record_standalone(
                category="security",
                action="auth.reauthenticate",
                outcome="denied",
                actor_id=user.id,
                ip=meta.ip,
            )
            # 403, not 401: the session is still valid, only the password was wrong.
            raise PermissionDeniedError(
                "The password is incorrect.", code="reauthentication_failed"
            ) from exc
        except AuthUnavailableError as exc:
            raise _unavailable() from exc
        if check.user_id != str(user.id):
            await self._revoke_quietly(check.access_token, "local")
            raise PermissionDeniedError(
                "Your password could not be confirmed.", code="reauthentication_failed"
            )
        # The check created a throwaway session; end it straight away.
        await self._revoke_quietly(check.access_token, "local")
        await self._limiter.reset(limits.REAUTH_PER_USER, subject)

    # -- session management --------------------------------------------------------------

    async def list_sessions(self, user: AuthenticatedUser) -> list[SessionInfo]:
        async with self._db.transaction() as session:
            records = await AuthSessionRepository(session).list_for_user(user.id)
        return [
            SessionInfo(
                id=record.id,
                created_at=record.created_at,
                last_active_at=record.last_active_at,
                device=describe_user_agent(record.user_agent),
                ip_prefix=ip_prefix(record.ip),
                current=record.id == user.session_id,
            )
            for record in records
        ]

    async def revoke_session(
        self, user: AuthenticatedUser, session_id: UUID, meta: RequestMeta
    ) -> None:
        if session_id == user.session_id:
            raise BadRequestError(
                "Use sign out to end the session you are using.", code="current_session"
            )
        async with self._db.transaction() as session:
            deleted = await AuthSessionRepository(session).delete(session_id, user.id)
            if not deleted:
                # Same answer for "not yours" and "does not exist".
                raise NotFoundError("Session not found.")
            await self._audit.record(
                session,
                category="security",
                action="auth.session_revoked",
                actor_id=user.id,
                target_type="session",
                target_id=str(session_id),
                ip=meta.ip,
            )

    async def revoke_other_sessions(self, user: AuthenticatedUser, meta: RequestMeta) -> int:
        async with self._db.transaction() as session:
            count = await AuthSessionRepository(session).delete_all_except(
                user.id, keep=user.session_id
            )
            await self._audit.record(
                session,
                category="security",
                action="auth.sessions_revoked",
                actor_id=user.id,
                ip=meta.ip,
                metadata={"count": count},
            )
            if count:
                await create_notification(
                    session,
                    user_id=user.id,
                    notification_type="security",
                    title="You signed out of your other devices",
                    body=f"{count} other session(s) were ended from this account.",
                )
        return count


def describe_user_agent(user_agent: str | None) -> str:
    """Coarse device label. The raw user agent is not returned."""
    if not user_agent:
        return "Unknown device"
    ua = user_agent.lower()
    browser = next(
        (
            name
            for key, name in (
                ("edg/", "Edge"),
                ("opr/", "Opera"),
                ("firefox/", "Firefox"),
                ("chrome/", "Chrome"),
                ("safari/", "Safari"),
            )
            if key in ua
        ),
        "Browser",
    )
    system = next(
        (
            name
            for key, name in (
                ("android", "Android"),
                ("iphone", "iPhone"),
                ("ipad", "iPad"),
                ("windows", "Windows"),
                ("mac os", "macOS"),
                ("linux", "Linux"),
            )
            if key in ua
        ),
        "Unknown OS",
    )
    return f"{browser} on {system}"
