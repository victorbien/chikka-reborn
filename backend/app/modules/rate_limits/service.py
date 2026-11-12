"""Database-backed rate limits shared across backend instances.

Every call runs in its own committed transaction, so a request that later fails and rolls
back still counts against the limit (otherwise failed logins would never be counted).
Subjects (emails, IPs, user ids) are stored only as keyed hashes.
"""

from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import RateLimitedError
from app.core.hashing import keyed_hash
from app.database.session import Database
from app.modules.rate_limits.repository import RateLimitRepository


@dataclass(frozen=True)
class Limit:
    scope: str
    max_attempts: int
    window_seconds: int
    lockout_seconds: int | None = None
    message: str | None = None


_SIGN_IN_LOCKED = "Too many sign-in attempts. Please wait before trying again."

# Values follow docs/api/authentication-api.md and FR-AUTH-006 / FR-AUTH-008.
REGISTER_PER_IP = Limit("auth.register.ip", 10, 3600)
LOGIN_PER_ACCOUNT = Limit("auth.login.account", 5, 900, 900, _SIGN_IN_LOCKED)
LOGIN_PER_IP = Limit("auth.login.ip", 20, 900, 900, _SIGN_IN_LOCKED)
REAUTH_PER_USER = Limit("auth.reauth.user", 5, 900, 900, "Too many password attempts.")
RESET_PER_IP = Limit("auth.reset.ip", 3, 3600)
RESET_PER_EMAIL = Limit("auth.reset.email", 3, 3600)
RESET_CONFIRM_PER_IP = Limit("auth.reset_confirm.ip", 10, 3600)
RESEND_PER_IP = Limit("auth.resend.ip", 3, 3600)
RESEND_PER_EMAIL = Limit("auth.resend.email", 3, 3600)
VERIFY_EMAIL_PER_IP = Limit("auth.verify_email.ip", 20, 3600)
REFRESH_PER_IP = Limit("auth.refresh.ip", 120, 3600)
OTP_SEND_PER_USER = Limit("auth.otp_send.user", 3, 1800)
OTP_VERIFY_PER_USER = Limit("auth.otp_verify.user", 20, 1800)
PROFILE_WRITE_PER_USER = Limit("profile.write.user", 60, 3600)
# FR-CONTACTS-001 AC1 and FR-CONTACTS-007 AC3. Searches and requests are counted per attempt.
CONTACT_SEARCH_PER_USER = Limit(
    "contacts.search.user", 20, 60, message="Too many searches. Please wait a moment."
)
CONTACT_REQUEST_PER_USER = Limit(
    "contacts.request.user",
    30,
    86400,
    message="You have reached today's limit of contact requests.",
)
CONTACT_WRITE_PER_USER = Limit("contacts.write.user", 200, 3600)


class RateLimiter:
    def __init__(self, database: Database, settings: Settings) -> None:
        self._database = database
        self._settings = settings

    def _subject(self, limit: Limit, subject: str) -> str:
        return keyed_hash(self._settings, f"ratelimit:{limit.scope}", subject.strip().lower())

    async def hit(self, limit: Limit, subject: str) -> None:
        """Count one attempt; raise 429 when the window's quota is exceeded."""
        async with self._database.transaction() as session:
            result = await RateLimitRepository(session).hit(
                limit.scope, self._subject(limit, subject), limit.window_seconds
            )
        if result.attempts > limit.max_attempts:
            raise RateLimitedError(result.retry_after, limit.message)

    async def ensure_not_locked(self, limit: Limit, subject: str) -> None:
        async with self._database.transaction() as session:
            locked_for = await RateLimitRepository(session).locked_for(
                limit.scope, self._subject(limit, subject)
            )
        if locked_for is not None:
            raise RateLimitedError(locked_for, limit.message)

    async def record_failure(self, limit: Limit, subject: str) -> bool:
        """Count a failure; start a lockout at the threshold. Returns True if it locked."""
        hashed = self._subject(limit, subject)
        async with self._database.transaction() as session:
            repository = RateLimitRepository(session)
            result = await repository.hit(limit.scope, hashed, limit.window_seconds)
            if limit.lockout_seconds and result.attempts >= limit.max_attempts:
                await repository.lock(limit.scope, hashed, limit.lockout_seconds)
                return True
        return False

    async def reset(self, limit: Limit, subject: str) -> None:
        async with self._database.transaction() as session:
            await RateLimitRepository(session).reset(limit.scope, self._subject(limit, subject))
