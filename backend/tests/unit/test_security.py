import uuid
from collections.abc import Callable
from datetime import timedelta

import pytest

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ServiceUnavailableError
from app.core.security import decode_access_token

USER = "11111111-1111-1111-1111-111111111111"
SESSION = "22222222-2222-2222-2222-222222222222"


def test_valid_token_yields_claims(settings: Settings, make_token: Callable[..., str]) -> None:
    claims = decode_access_token(make_token(sub=USER, session_id=SESSION), settings)
    assert claims.user_id == uuid.UUID(USER)
    assert claims.session_id == uuid.UUID(SESSION)
    assert claims.email == "fake.user@example.com"


def test_role_claims_in_token_are_not_part_of_identity(
    settings: Settings, make_token: Callable[..., str]
) -> None:
    # Roles are loaded from the database; token metadata (user-editable) is ignored.
    token = make_token(sub=USER, app_metadata={"role": "admin"}, user_metadata={"role": "admin"})
    claims = decode_access_token(token, settings)
    assert not hasattr(claims, "role")


def test_token_without_session_id_is_rejected(
    settings: Settings, make_token: Callable[..., str]
) -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token(make_token(sub=USER, session_id=None), settings)


def test_non_uuid_subject_is_rejected(settings: Settings, make_token: Callable[..., str]) -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token(make_token(sub="user-1"), settings)


def test_expired_token_is_rejected(settings: Settings, make_token: Callable[..., str]) -> None:
    token = make_token(expires_in=timedelta(minutes=-1))
    with pytest.raises(AuthenticationError, match="expired") as raised:
        decode_access_token(token, settings)
    assert raised.value.code == "token_expired"


def test_wrong_signature_is_rejected(settings: Settings, make_token: Callable[..., str]) -> None:
    token = make_token(secret="a-different-secret-that-is-long-enough!!")
    with pytest.raises(AuthenticationError):
        decode_access_token(token, settings)


def test_wrong_audience_is_rejected(settings: Settings, make_token: Callable[..., str]) -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token(make_token(audience="somebody-else"), settings)


def test_garbage_token_is_rejected(settings: Settings) -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token("not.a.jwt", settings)


def test_missing_secret_fails_closed() -> None:
    unconfigured = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(ServiceUnavailableError):
        decode_access_token("anything", unconfigured)
