"""Deployment hardening: body limits, security headers and the preflight check."""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI, Request

from app.core.body_limit import (
    AVATAR_LIMIT,
    DEFAULT_LIMIT,
    UPLOAD_LIMIT,
    WEBHOOK_LIMIT,
    limit_for,
)
from app.core.config import Settings
from app.core.middleware import register_middleware
from app.preflight import check


def hosted(**values: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "production",
        "app_secret_key": "k" * 40,
        "database_url": "postgresql://u:p@db.example.com:5432/postgres",
        "supabase_url": "https://abc.supabase.co",
        "supabase_anon_key": "anon",
        "supabase_service_role_key": "service",
        "cors_origins": ["https://app.example.com"],
        "frontend_base_url": "https://app.example.com",
    }
    return Settings(_env_file=None, **{**base, **values})  # type: ignore[call-arg, arg-type]


def make_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    register_middleware(app, settings)

    @app.post("/api/v1/echo")
    async def echo(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.post("/api/v1/webhooks/twilio/inbound")
    async def hook(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    return app


def client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example.com"
    )


def test_limits_by_route() -> None:
    assert limit_for("/api/v1/auth/login") == DEFAULT_LIMIT
    assert limit_for("/api/v1/conversations/abc/attachments") == UPLOAD_LIMIT
    assert limit_for("/api/v1/users/me/avatar") == AVATAR_LIMIT
    assert limit_for("/api/v1/webhooks/twilio/status") == WEBHOOK_LIMIT


async def test_declared_oversized_body_is_refused() -> None:
    async with client(make_app(hosted())) as http:
        response = await http.post("/api/v1/echo", content=b"x" * (DEFAULT_LIMIT + 1))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_chunked_oversized_body_is_refused_without_a_content_length() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(DEFAULT_LIMIT // 1024 + 2):
            yield b"x" * 1024

    async with client(make_app(hosted())) as http:
        response = await http.post("/api/v1/echo", content=chunks())
    assert response.status_code == 413


async def test_body_within_the_limit_passes() -> None:
    async with client(make_app(hosted())) as http:
        response = await http.post("/api/v1/echo", content=b"x" * 1000)
    assert response.status_code == 200
    assert response.json() == {"size": 1000}


async def test_webhook_limit_is_smaller_than_the_default() -> None:
    async with client(make_app(hosted())) as http:
        response = await http.post(
            "/api/v1/webhooks/twilio/inbound", content=b"x" * (WEBHOOK_LIMIT + 1)
        )
    assert response.status_code == 413


async def test_hosted_responses_carry_hsts_and_frame_protection() -> None:
    async with client(make_app(hosted())) as http:
        response = await http.post("/api/v1/echo", content=b"")
    assert response.headers["x-frame-options"] == "DENY"
    assert "max-age=" in response.headers["strict-transport-security"]
    assert response.headers["x-request-id"]


async def test_local_development_does_not_send_hsts() -> None:
    local = Settings(_env_file=None, app_env="development")  # type: ignore[call-arg]
    async with client(make_app(local)) as http:
        response = await http.post("/api/v1/echo", content=b"")
    assert "strict-transport-security" not in response.headers


def test_a_complete_hosted_configuration_has_no_blocking_problems() -> None:
    problems, warnings = check(hosted())
    assert problems == []
    assert any("simulation" in w for w in warnings)


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"app_env": "development"}, "APP_ENV"),
        ({"database_url": None}, "DATABASE_URL is not set"),
        ({"database_url": "postgresql://u:p@localhost:5432/x"}, "local host"),
        ({"supabase_url": "http://abc.supabase.co"}, "SUPABASE_URL must"),
        ({"supabase_service_role_key": None}, "SUPABASE_SERVICE_ROLE_KEY"),
        ({"cors_origins": ["http://localhost:5173"]}, "CORS_ORIGINS contains"),
        ({"cors_origins": ["https://other.example.com"]}, "not listed in CORS_ORIGINS"),
        ({"frontend_base_url": "http://app.example.com"}, "FRONTEND_BASE_URL must"),
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"log_level": "DEBUG"}, "LOG_LEVEL"),
    ],
)
def test_unsafe_hosted_configuration_is_blocked(override: dict[str, object], expected: str) -> None:
    problems, _ = check(hosted(**override))
    assert any(expected in problem for problem in problems), problems


def test_preflight_output_never_contains_secret_values() -> None:
    problems, warnings = check(hosted(cookie_secure=False, supabase_service_role_key=None))
    text = " ".join(problems + warnings)
    for secret in ("k" * 40, "anon", "p@db.example.com"):
        assert secret not in text


def test_live_sms_needs_a_public_https_callback_origin() -> None:
    settings = hosted(
        sms_provider_mode="live",
        sms_live_confirmed=True,
        twilio_account_sid="ACtest",
        twilio_auth_token="token",
        sms_public_base_url="http://api.example.com",
    )
    problems, warnings = check(settings)
    assert any("SMS_PUBLIC_BASE_URL" in p for p in problems)
    assert any("Live SMS is configured" in w for w in warnings)
