"""Pre-deployment configuration check: `python -m app.preflight`.

Run it in the release step and as the container entrypoint's first command. It loads the real
settings, refuses configurations that are unsafe for a hosted environment and prints warnings for
choices an operator should make on purpose (simulation providers). It never prints a value, only
setting names, so its output is safe to keep in build logs.

Exit code 0: deployable. 1: at least one blocking problem.
"""

import sys
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.core.config import Settings

HOSTED_ENVIRONMENTS = ("staging", "production")
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})  # noqa: S104


def _is_https_public(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and (parts.hostname or "") not in _LOCAL_HOSTS


def check(settings: Settings) -> tuple[list[str], list[str]]:
    """Return (blocking problems, warnings). Messages name settings, never values."""
    problems: list[str] = []
    warnings: list[str] = []

    if settings.app_env not in HOSTED_ENVIRONMENTS:
        problems.append("APP_ENV must be 'staging' or 'production' for a hosted deployment")

    required = {
        "DATABASE_URL": settings.database_url,
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_ANON_KEY": settings.supabase_anon_key,
        "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
    }
    problems += [f"{name} is not set" for name, value in required.items() if value is None]

    if settings.supabase_url and not _is_https_public(settings.supabase_url):
        problems.append("SUPABASE_URL must be a public https URL")
    if settings.database_url and urlsplit(settings.database_url).hostname in _LOCAL_HOSTS:
        problems.append("DATABASE_URL points at a local host")
    if settings.supabase_jwt_secret is not None:
        warnings.append(
            "SUPABASE_JWT_SECRET is set (legacy HS256). Prefer asymmetric signing keys and "
            "remove it."
        )

    if not settings.cors_origins:
        problems.append("CORS_ORIGINS is empty")
    problems += [
        "CORS_ORIGINS contains a non-https or local origin"
        for origin in settings.cors_origins
        if not _is_https_public(origin)
    ][:1]
    if not _is_https_public(settings.frontend_base_url):
        problems.append("FRONTEND_BASE_URL must be a public https URL")
    else:
        frontend = urlsplit(settings.frontend_base_url)
        frontend_origin = f"{frontend.scheme}://{frontend.netloc}"
        if frontend_origin not in settings.cors_origins:
            problems.append("FRONTEND_BASE_URL's origin is not listed in CORS_ORIGINS")

    if settings.cookie_secure is False:
        problems.append("COOKIE_SECURE=false is not allowed in a hosted environment")
    if settings.log_level == "DEBUG":
        problems.append("LOG_LEVEL=DEBUG is not allowed in a hosted environment")
    if not settings.sms_worker_enabled:
        warnings.append("SMS_WORKER_ENABLED=false: nothing dispatches queued SMS from this process")
    if not settings.notifications_worker_enabled:
        warnings.append("NOTIFICATIONS_WORKER_ENABLED=false: notifications are not delivered")

    if settings.sms_provider_mode == "live":
        if not settings.sms_public_base_url or not _is_https_public(settings.sms_public_base_url):
            problems.append("SMS_PUBLIC_BASE_URL must be a public https URL for live SMS")
        warnings.append(
            "Live SMS is configured. Confirm approval, sender registration and recipient "
            "consent per docs/deployment/twilio-configuration.md."
        )
    else:
        warnings.append("SMS runs in simulation: nothing is sent to real phones")
    if settings.ai_provider_mode == "mock":
        warnings.append("AI runs in mock mode: canned drafts, no model is called")
    if settings.email_provider_mode == "mock":
        warnings.append("Email runs in mock mode: no email is sent (sign-up links will not arrive)")
    return problems, warnings


def main() -> int:
    try:
        settings = Settings()
    except ValidationError as exc:
        print("BLOCKING: configuration is invalid:")
        for error in exc.errors():
            where = ".".join(str(part) for part in error["loc"]) or "settings"
            print(f"  - {where}: {error['msg']}")
        return 1

    problems, warnings = check(settings)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for problem in problems:
        print(f"BLOCKING: {problem}")
    if problems:
        return 1
    print(f"preflight ok for APP_ENV={settings.app_env}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
