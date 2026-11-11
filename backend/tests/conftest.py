import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_account_lookup
from app.core.config import Settings
from app.core.security import AuthenticatedUser, TokenClaims
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


class FakeAccountLookup:
    """Database-free stand-in for AccountResolver: every verified token maps to an account."""

    def __init__(self) -> None:
        self.roles: dict[uuid.UUID, str] = {}
        self.statuses: dict[uuid.UUID, str] = {}
        self.revoked_sessions: set[uuid.UUID] = set()

    async def resolve(self, claims: TokenClaims) -> AuthenticatedUser:
        from app.core.exceptions import AuthenticationError, PermissionDeniedError

        if claims.session_id in self.revoked_sessions:
            raise AuthenticationError("Your session has ended.", code="session_revoked")
        status = self.statuses.get(claims.user_id, "active")
        if status in ("deleted", "suspended"):
            raise PermissionDeniedError(
                "This account is not available.", code="account_unavailable"
            )
        return AuthenticatedUser(
            id=claims.user_id,
            session_id=claims.session_id,
            email=claims.email,
            role=self.roles.get(claims.user_id, "user"),  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            onboarded=True,
        )


@pytest.fixture
def account_lookup() -> FakeAccountLookup:
    return FakeAccountLookup()


@pytest.fixture
def app(settings: Settings, account_lookup: FakeAccountLookup) -> FastAPI:
    application = create_app(settings)
    application.dependency_overrides[get_account_lookup] = lambda: account_lookup
    return application


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
        session_id: str | None = "00000000-0000-0000-0000-0000000000aa",
        secret: str = TEST_JWT_SECRET,
        audience: str = "authenticated",
        expires_in: timedelta = timedelta(minutes=5),
        app_metadata: dict[str, Any] | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> str:
        claims: dict[str, Any] = {
            "sub": sub,
            "aud": audience,
            "email": "fake.user@example.com",
            "exp": datetime.now(UTC) + expires_in,
            "app_metadata": app_metadata or {},
            "user_metadata": user_metadata or {},
        }
        if session_id is not None:
            claims["session_id"] = session_id
        return jwt.encode(claims, secret, algorithm="HS256")

    return _make
