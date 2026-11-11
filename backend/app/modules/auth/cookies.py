"""Refresh-token cookie (ADL-011). The access token is returned in the body and kept in
memory by the SPA; the refresh token never reaches script-readable storage."""

from fastapi import Request, Response

from app.core.config import Settings
from app.core.exceptions import PermissionDeniedError

REFRESH_COOKIE = "chikka_refresh"
COOKIE_PATH = "/api/v1/auth"
# Sliding: each refresh re-issues the cookie, so 7 idle days end the session (FR-AUTH-004 AC3).
REFRESH_MAX_AGE = 7 * 24 * 3600
CSRF_HEADER = "X-Chikka-CSRF"


def set_refresh_cookie(response: Response, settings: Settings, refresh_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=REFRESH_MAX_AGE,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
    )


def require_csrf_header(request: Request) -> None:
    """Cookie-authenticated endpoints need a custom header. Browsers only send one after a
    CORS preflight that our explicit origin list approves, so other sites cannot forge it."""
    if request.headers.get(CSRF_HEADER) != "1":
        raise PermissionDeniedError("Missing request header.", code="csrf_required")
