from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

TEST_JWT_SECRET = "test-only-secret-with-at-least-32-bytes!"  # fake, never a real credential


@pytest.fixture
def settings() -> Settings:
    # _env_file=None keeps a developer's local .env out of the tests.
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        cors_origins=["http://localhost:5173"],
        supabase_jwt_secret=TEST_JWT_SECRET,  # type: ignore[arg-type]
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Unhandled errors must become 500 responses, as in production, not test exceptions.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def make_token() -> Callable[..., str]:
    def _make(
        *,
        sub: str = "00000000-0000-0000-0000-000000000001",
        secret: str = TEST_JWT_SECRET,
        audience: str = "authenticated",
        expires_in: timedelta = timedelta(minutes=5),
        app_metadata: dict[str, Any] | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> str:
        claims: dict[str, Any] = {
            "sub": sub,
            "aud": audience,
            "email": "fake.user@example.test",
            "exp": datetime.now(UTC) + expires_in,
            "app_metadata": app_metadata or {},
            "user_metadata": user_metadata or {},
        }
        return jwt.encode(claims, secret, algorithm="HS256")

    return _make
