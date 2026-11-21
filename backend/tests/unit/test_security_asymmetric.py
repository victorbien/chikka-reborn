"""ES256/RS256 access tokens verified against the project's published keys (JWKS).

Keys are generated per test run; the JWKS client is replaced so nothing touches the network.
"""

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core import security
from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ServiceUnavailableError
from app.core.security import decode_access_token

PROJECT = "https://example-project.supabase.co"
ISSUER = f"{PROJECT}/auth/v1"
USER = "11111111-1111-1111-1111-111111111111"
SESSION = "22222222-2222-2222-2222-222222222222"
KID = "test-key-1"

PROJECT_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


class FakeJwksClient:
    """Stands in for PyJWKClient: serves the project's public key for one kid."""

    def __init__(self, *, unreachable: bool = False) -> None:
        self.unreachable = unreachable
        self.urls: list[str] = []

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        if self.unreachable:
            raise jwt.PyJWKClientConnectionError("down")
        kid = jwt.get_unverified_header(token).get("kid")
        if kid != KID:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        public = jwt.algorithms.ECAlgorithm.to_jwk(PROJECT_KEY.public_key(), as_dict=True)
        return jwt.PyJWK({**public, "kid": KID, "alg": "ES256", "use": "sig"})


@pytest.fixture
def jwks(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeJwksClient]:
    fake = FakeJwksClient()

    def _client(url: str) -> FakeJwksClient:
        fake.urls.append(url)
        return fake

    monkeypatch.setattr(security, "_jwks_client", _client)
    yield fake


@pytest.fixture
def asym_settings() -> Settings:
    # Asymmetric-only project: no legacy secret at all.
    return Settings(_env_file=None, app_env="test", supabase_url=PROJECT)  # type: ignore[call-arg]


@pytest.fixture
def es256_token() -> Callable[..., str]:
    def _make(
        *,
        key: Any = PROJECT_KEY,
        kid: str = KID,
        issuer: str = ISSUER,
        audience: str = "authenticated",
        expires_in: timedelta = timedelta(minutes=5),
        algorithm: str = "ES256",
    ) -> str:
        claims = {
            "sub": USER,
            "session_id": SESSION,
            "aud": audience,
            "iss": issuer,
            "email": "fake.user@example.com",
            "exp": datetime.now(UTC) + expires_in,
        }
        return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": kid})

    return _make


def test_es256_token_from_project_keys_is_accepted(
    asym_settings: Settings, jwks: FakeJwksClient, es256_token: Callable[..., str]
) -> None:
    claims = decode_access_token(es256_token(), asym_settings)
    assert claims.user_id == uuid.UUID(USER)
    assert claims.session_id == uuid.UUID(SESSION)
    assert jwks.urls == [f"{ISSUER}/.well-known/jwks.json"]


def test_explicit_jwks_url_overrides_the_default(
    jwks: FakeJwksClient, es256_token: Callable[..., str]
) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        app_env="test",
        supabase_url=PROJECT,
        supabase_jwks_url="https://keys.example.test/jwks.json",
    )
    decode_access_token(es256_token(), settings)
    assert jwks.urls == ["https://keys.example.test/jwks.json"]


def test_token_signed_by_another_key_is_rejected(
    asym_settings: Settings, jwks: FakeJwksClient, es256_token: Callable[..., str]
) -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token(es256_token(key=OTHER_KEY), asym_settings)


def test_unknown_key_id_is_rejected(
    asym_settings: Settings, jwks: FakeJwksClient, es256_token: Callable[..., str]
) -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token(es256_token(kid="someone-elses-key"), asym_settings)


def test_token_from_another_project_is_rejected(
    asym_settings: Settings, jwks: FakeJwksClient, es256_token: Callable[..., str]
) -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token(es256_token(issuer="https://other.supabase.co/auth/v1"), asym_settings)


def test_wrong_audience_and_expiry_are_enforced(
    asym_settings: Settings, jwks: FakeJwksClient, es256_token: Callable[..., str]
) -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token(es256_token(audience="somebody-else"), asym_settings)
    with pytest.raises(AuthenticationError, match="expired"):
        decode_access_token(es256_token(expires_in=timedelta(minutes=-1)), asym_settings)


def test_unsigned_token_is_rejected(asym_settings: Settings, jwks: FakeJwksClient) -> None:
    token = jwt.encode({"sub": USER, "session_id": SESSION, "aud": "authenticated"}, None, "none")
    with pytest.raises(AuthenticationError):
        decode_access_token(token, asym_settings)


def test_hs256_token_is_rejected_when_no_shared_secret_is_configured(
    asym_settings: Settings, jwks: FakeJwksClient
) -> None:
    # Without this, a token "signed" with a guessable value could slip through.
    token = jwt.encode(
        {"sub": USER, "session_id": SESSION, "aud": "authenticated", "exp": 9999999999},
        "guess",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(token, asym_settings)


def test_unreachable_key_endpoint_is_a_503_not_a_401(
    asym_settings: Settings, jwks: FakeJwksClient, es256_token: Callable[..., str]
) -> None:
    jwks.unreachable = True
    with pytest.raises(ServiceUnavailableError) as raised:
        decode_access_token(es256_token(), asym_settings)
    assert raised.value.code == "auth_unavailable"


def test_legacy_hs256_still_works_alongside_project_keys(
    settings: Settings, jwks: FakeJwksClient, make_token: Callable[..., str]
) -> None:
    # Projects migrating to signing keys keep accepting tokens signed with the legacy secret.
    claims = decode_access_token(make_token(sub=USER, session_id=SESSION), settings)
    assert claims.user_id == uuid.UUID(USER)
    assert jwks.urls == []
