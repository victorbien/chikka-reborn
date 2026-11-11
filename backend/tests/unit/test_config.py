import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg, arg-type]


def test_defaults_are_safe() -> None:
    settings = make()
    assert settings.sms_provider_mode == "mock"
    assert settings.sms_mode == "simulation"
    assert settings.database_url is None
    assert settings.docs_enabled is True


def test_cors_origins_accept_comma_separated_string() -> None:
    settings = make(cors_origins="http://a.test, http://b.test")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_wildcard_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make(cors_origins="*")


def test_blank_values_from_env_example_mean_unset() -> None:
    settings = make(database_url="", supabase_jwt_secret="  ")
    assert settings.database_url is None
    assert settings.supabase_jwt_secret is None


def test_database_url_is_upgraded_to_async_driver() -> None:
    settings = make(database_url="postgresql://user:pw@db.test:5432/postgres")
    assert settings.database_url == "postgresql+asyncpg://user:pw@db.test:5432/postgres"


def test_non_postgres_database_url_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make(database_url="mysql://user:pw@db.test/x")


def test_live_sms_requires_explicit_confirmation() -> None:
    with pytest.raises(ValidationError, match="SMS_LIVE_CONFIRMED"):
        make(sms_provider_mode="live")
    assert make(sms_provider_mode="live", sms_live_confirmed=True).sms_mode == "live"


def test_docs_are_disabled_in_production() -> None:
    assert make(app_env="production").docs_enabled is False


def test_secret_is_not_leaked_in_repr() -> None:
    settings = make(supabase_jwt_secret="super-secret-value")
    assert "super-secret-value" not in repr(settings)
