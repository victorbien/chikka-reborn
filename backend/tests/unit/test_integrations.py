import json
import logging
import sys
from typing import Any

import httpx
import pytest

from app.api.container import build_providers
from app.core.config import Settings
from app.core.exceptions import UnprocessableError
from app.core.logging import configure_logging
from app.integrations.auth_provider import (
    AuthUnavailableError,
    EmailNotConfirmedError,
    InvalidCredentialsError,
    InvalidTokenError,
    SupabaseAuthProvider,
    UnconfiguredAuthProvider,
    WeakPasswordError,
)
from app.integrations.otp_delivery import (
    OtpDeliveryUnavailableError,
    SimulatedInbox,
    SimulatedOtpDelivery,
    UnavailableLiveOtpDelivery,
)
from app.integrations.storage_provider import StorageError, UnconfiguredStorageProvider
from app.modules.auth.phone_service import normalise_phone


def _provider(handler: Any) -> SupabaseAuthProvider:
    return SupabaseAuthProvider(
        base_url="http://auth.test",
        anon_key="anon",
        service_role_key=None,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _json(status: int, body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        status, content=json.dumps(body), headers={"content-type": "application/json"}
    )


@pytest.mark.parametrize(
    ("status", "code", "error"),
    [
        (400, "invalid_credentials", InvalidCredentialsError),
        (400, "email_not_confirmed", EmailNotConfirmedError),
        (400, "user_banned", InvalidCredentialsError),
        (500, "boom", AuthUnavailableError),
        (503, "", AuthUnavailableError),
    ],
)
async def test_sign_in_maps_provider_errors(status: int, code: str, error: type[Exception]) -> None:
    provider = _provider(lambda _request: _json(status, {"error_code": code}))
    with pytest.raises(error):
        await provider.sign_in(email="a@example.com", password="x")


async def test_network_failure_is_unavailable_not_invalid() -> None:
    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(AuthUnavailableError):
        await _provider(fail).sign_in(email="a@example.com", password="x")


async def test_sign_in_sends_the_anon_key_and_parses_the_session() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["apikey"] = request.headers["apikey"]
        seen["grant"] = request.url.params["grant_type"]
        return _json(
            200,
            {
                "access_token": "a",
                "refresh_token": "r",
                "expires_in": 60,
                "user": {"id": "u1", "email": "a@example.com"},
            },
        )

    session = await _provider(handler).sign_in(email="a@example.com", password="x")
    assert (session.access_token, session.refresh_token, session.user_id) == ("a", "r", "u1")
    assert seen == {"apikey": "anon", "grant": "password"}


async def test_signup_weak_password_and_verify_failures() -> None:
    with pytest.raises(WeakPasswordError):
        await _provider(lambda _r: _json(422, {"error_code": "weak_password"})).sign_up(
            email="a@example.com", password="x", display_name="A B", redirect_to="http://x"
        )
    with pytest.raises(InvalidTokenError):
        await _provider(lambda _r: _json(403, {"error_code": "otp_expired"})).verify_token_hash(
            "t" * 10, "signup"
        )


async def test_admin_calls_need_the_service_role_key() -> None:
    with pytest.raises(AuthUnavailableError):
        await _provider(lambda _r: _json(200, {})).disable_user("u1")


async def test_unconfigured_providers_fail_loudly() -> None:
    with pytest.raises(AuthUnavailableError):
        await UnconfiguredAuthProvider().sign_in(email="a@example.com", password="x")
    with pytest.raises(StorageError):
        await UnconfiguredStorageProvider().upload("p", b"", "image/webp")


async def test_live_otp_delivery_never_falls_back_to_simulation() -> None:
    with pytest.raises(OtpDeliveryUnavailableError):
        await UnavailableLiveOtpDelivery().deliver(
            user_id="u", e164="+639171230001", code="123456", ttl_seconds=600
        )


async def test_simulated_delivery_stores_masked_recipient_only() -> None:
    inbox = SimulatedInbox()
    await SimulatedOtpDelivery(inbox).deliver(
        user_id="u", e164="+639171230001", code="123456", ttl_seconds=600
    )
    (message,) = inbox.list_for("u")
    assert message.masked_to == "+63****0001"
    assert message.code == "123456"


def test_provider_selection_follows_configuration() -> None:
    bare = build_providers(Settings(_env_file=None))  # type: ignore[call-arg]
    assert isinstance(bare.auth, UnconfiguredAuthProvider)
    assert isinstance(bare.storage, UnconfiguredStorageProvider)
    assert bare.otp.mode == "simulated"

    live = build_providers(
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            sms_provider_mode="live",
            sms_live_confirmed=True,
            twilio_account_sid="ACfake",
            twilio_auth_token="fake-token",
            sms_public_base_url="https://api.example.test",
        )
    )
    assert isinstance(live.otp, UnavailableLiveOtpDelivery)
    assert live.sms is not None
    assert live.sms.name == "twilio"


@pytest.mark.parametrize(
    ("raw", "e164", "region"),
    [("+63 917 123 0001", "+639171230001", "PH"), ("+1-415-555-2671", "+14155552671", "US")],
)
def test_phone_normalisation(raw: str, e164: str, region: str) -> None:
    assert normalise_phone(raw) == (e164, region)


@pytest.mark.parametrize("raw", ["09171230001", "+63", "+00000000", "+63 abc"])
def test_phone_normalisation_rejects_bad_numbers(raw: str) -> None:
    with pytest.raises(UnprocessableError):
        normalise_phone(raw)


def test_log_handler_writes_to_the_current_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    original = sys.stdout
    logging.getLogger("t").info("first")
    assert "first" in capsys.readouterr().out
    assert sys.stdout is original
