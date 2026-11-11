"""Identity provider interface and its Supabase Auth (GoTrue) implementation.

Passwords are only ever forwarded to the provider over HTTPS. Nothing here stores, logs or
returns a password, OTP or token other than to the caller that needs it.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

logger = logging.getLogger(__name__)

SignOutScope = Literal["local", "global", "others"]
TokenType = Literal["signup", "recovery"]


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: str
    email: str | None


class AuthProviderError(Exception):
    """Base for provider failures. Messages are safe to log; they never carry credentials."""


class InvalidCredentialsError(AuthProviderError):
    pass


class EmailNotConfirmedError(AuthProviderError):
    pass


class InvalidTokenError(AuthProviderError):
    """Expired, reused or unknown one-time token, or refresh token."""


class WeakPasswordError(AuthProviderError):
    pass


class AuthUnavailableError(AuthProviderError):
    """Provider unreachable, misconfigured or returning server errors."""


class AuthProvider(Protocol):
    async def sign_up(
        self, *, email: str, password: str, display_name: str, redirect_to: str
    ) -> str:
        """Create the account and return its user id.

        For an address that is already registered the provider answers like a new sign-up
        (with a throwaway id) so callers cannot enumerate accounts.
        """
        ...

    async def sign_in(self, *, email: str, password: str) -> AuthSession: ...

    async def refresh(self, refresh_token: str) -> AuthSession: ...

    async def sign_out(self, access_token: str, scope: SignOutScope) -> None: ...

    async def request_recovery(self, *, email: str, redirect_to: str) -> None: ...

    async def resend_signup(self, *, email: str, redirect_to: str) -> None: ...

    async def verify_token_hash(self, token_hash: str, token_type: TokenType) -> AuthSession: ...

    async def update_password(self, access_token: str, new_password: str) -> None: ...

    async def disable_user(self, user_id: str) -> None:
        """Block sign-in permanently and replace the email with a non-identifying address."""
        ...


class UnconfiguredAuthProvider:
    """Used when Supabase settings are missing. Fails loudly instead of pretending to work."""

    async def _fail(self) -> Any:
        raise AuthUnavailableError("Supabase Auth is not configured")

    async def sign_up(self, **_: Any) -> str:
        return str(await self._fail())

    async def sign_in(self, **_: Any) -> AuthSession:
        return await self._fail()  # type: ignore[no-any-return]

    async def refresh(self, refresh_token: str) -> AuthSession:
        return await self._fail()  # type: ignore[no-any-return]

    async def sign_out(self, access_token: str, scope: SignOutScope) -> None:
        await self._fail()

    async def request_recovery(self, **_: Any) -> None:
        await self._fail()

    async def resend_signup(self, **_: Any) -> None:
        await self._fail()

    async def verify_token_hash(self, token_hash: str, token_type: TokenType) -> AuthSession:
        return await self._fail()  # type: ignore[no-any-return]

    async def update_password(self, access_token: str, new_password: str) -> None:
        await self._fail()

    async def disable_user(self, user_id: str) -> None:
        await self._fail()


# Ban long enough to be permanent for our purposes; the profile row is the source of truth.
_BAN_DURATION = "876000h"


def anonymised_email(user_id: str) -> str:
    """Replacement address after deletion: keeps the auth row valid without personal data."""
    return f"deleted-{user_id}@deleted.chikka-reborn.invalid"


class SupabaseAuthProvider:
    def __init__(
        self,
        *,
        base_url: str,
        anon_key: str,
        service_role_key: str | None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/") + "/auth/v1"
        self._anon_key = anon_key
        self._service_role_key = service_role_key
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- plumbing ------------------------------------------------------------------------

    def _headers(self, bearer: str | None = None, *, admin: bool = False) -> dict[str, str]:
        if admin:
            if not self._service_role_key:
                raise AuthUnavailableError("Service role key is not configured")
            key = self._service_role_key
            return {"apikey": key, "Authorization": f"Bearer {key}"}
        headers = {"apikey": self._anon_key}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str],
    ) -> httpx.Response:
        try:
            response = await self._client.request(
                method, f"{self._base}{path}", json=json, params=params, headers=headers
            )
        except httpx.HTTPError as exc:
            logger.warning("auth provider unreachable", extra={"error_type": type(exc).__name__})
            raise AuthUnavailableError("Auth provider unreachable") from exc
        if response.status_code >= 500:
            logger.warning("auth provider error", extra={"status_code": response.status_code})
            raise AuthUnavailableError("Auth provider error")
        return response

    @staticmethod
    def _error_code(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return ""
        if isinstance(body, dict):
            return str(body.get("error_code") or body.get("error") or "")
        return ""

    @staticmethod
    def _session(body: dict[str, Any]) -> AuthSession:
        try:
            user = body["user"]
            return AuthSession(
                access_token=str(body["access_token"]),
                refresh_token=str(body["refresh_token"]),
                expires_in=int(body.get("expires_in", 3600)),
                user_id=str(user["id"]),
                email=user.get("email"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthUnavailableError("Unexpected auth provider response") from exc

    def _raise_for_credentials(self, response: httpx.Response) -> None:
        code = self._error_code(response)
        if code == "email_not_confirmed":
            raise EmailNotConfirmedError
        if code == "weak_password":
            raise WeakPasswordError
        raise InvalidCredentialsError

    # -- operations ----------------------------------------------------------------------

    async def sign_up(
        self, *, email: str, password: str, display_name: str, redirect_to: str
    ) -> str:
        response = await self._request(
            "POST",
            "/signup",
            json={"email": email, "password": password, "data": {"display_name": display_name}},
            params={"redirect_to": redirect_to},
            headers=self._headers(),
        )
        if response.status_code >= 400:
            if self._error_code(response) == "weak_password":
                raise WeakPasswordError
            # Anything else (including "already registered" on some configurations) is treated
            # as a provider fault; callers must not reveal which.
            logger.warning("sign-up rejected", extra={"status_code": response.status_code})
            raise AuthUnavailableError("Sign-up rejected")
        body = response.json()
        user = body.get("user", body) if isinstance(body, dict) else {}
        user_id = user.get("id") if isinstance(user, dict) else None
        if not user_id:
            raise AuthUnavailableError("Unexpected auth provider response")
        return str(user_id)

    async def sign_in(self, *, email: str, password: str) -> AuthSession:
        response = await self._request(
            "POST",
            "/token",
            params={"grant_type": "password"},
            json={"email": email, "password": password},
            headers=self._headers(),
        )
        if response.status_code >= 400:
            self._raise_for_credentials(response)
        return self._session(response.json())

    async def refresh(self, refresh_token: str) -> AuthSession:
        response = await self._request(
            "POST",
            "/token",
            params={"grant_type": "refresh_token"},
            json={"refresh_token": refresh_token},
            headers=self._headers(),
        )
        if response.status_code >= 400:
            raise InvalidTokenError
        return self._session(response.json())

    async def sign_out(self, access_token: str, scope: SignOutScope) -> None:
        response = await self._request(
            "POST", "/logout", params={"scope": scope}, headers=self._headers(access_token)
        )
        if response.status_code in (401, 403):
            raise InvalidTokenError
        if response.status_code >= 400:
            raise AuthUnavailableError("Sign-out failed")

    async def request_recovery(self, *, email: str, redirect_to: str) -> None:
        response = await self._request(
            "POST",
            "/recover",
            json={"email": email},
            params={"redirect_to": redirect_to},
            headers=self._headers(),
        )
        # 4xx here means "no such user" or throttling; the caller answers neutrally either way.
        if response.status_code >= 400:
            logger.info("recovery not sent", extra={"status_code": response.status_code})

    async def resend_signup(self, *, email: str, redirect_to: str) -> None:
        response = await self._request(
            "POST",
            "/resend",
            json={"type": "signup", "email": email},
            params={"redirect_to": redirect_to},
            headers=self._headers(),
        )
        if response.status_code >= 400:
            logger.info("verification not resent", extra={"status_code": response.status_code})

    async def verify_token_hash(self, token_hash: str, token_type: TokenType) -> AuthSession:
        response = await self._request(
            "POST",
            "/verify",
            json={"type": token_type, "token_hash": token_hash},
            headers=self._headers(),
        )
        if response.status_code >= 400:
            raise InvalidTokenError
        return self._session(response.json())

    async def update_password(self, access_token: str, new_password: str) -> None:
        response = await self._request(
            "PUT",
            "/user",
            json={"password": new_password},
            headers=self._headers(access_token),
        )
        if response.status_code >= 400:
            code = self._error_code(response)
            if code in ("weak_password", "same_password"):
                raise WeakPasswordError
            raise InvalidTokenError

    async def disable_user(self, user_id: str) -> None:
        response = await self._request(
            "PUT",
            f"/admin/users/{user_id}",
            json={
                "ban_duration": _BAN_DURATION,
                "email": anonymised_email(user_id),
                "email_confirm": True,
                "user_metadata": {},
            },
            headers=self._headers(admin=True),
        )
        if response.status_code >= 400:
            raise AuthUnavailableError("Could not disable the account")
