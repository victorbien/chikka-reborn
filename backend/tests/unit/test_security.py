from collections.abc import Callable
from datetime import timedelta

import pytest

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ServiceUnavailableError
from app.core.security import decode_access_token


def test_valid_token_yields_user(settings: Settings, make_token: Callable[..., str]) -> None:
    user = decode_access_token(make_token(sub="user-1"), settings)
    assert user.id == "user-1"
    assert user.email == "fake.user@example.test"
    assert user.role == "user"


def test_admin_role_comes_from_app_metadata(
    settings: Settings, make_token: Callable[..., str]
) -> None:
    token = make_token(app_metadata={"role": "admin"})
    assert decode_access_token(token, settings).role == "admin"


def test_admin_role_in_user_metadata_is_ignored(
    settings: Settings, make_token: Callable[..., str]
) -> None:
    token = make_token(user_metadata={"role": "admin"})
    assert decode_access_token(token, settings).role == "user"


def test_expired_token_is_rejected(settings: Settings, make_token: Callable[..., str]) -> None:
    token = make_token(expires_in=timedelta(minutes=-1))
    with pytest.raises(AuthenticationError, match="expired"):
        decode_access_token(token, settings)


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
