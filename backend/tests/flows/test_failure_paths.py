"""Failure and edge paths: provider outages, expiry, cooldowns, suspended accounts."""

import uuid

import pytest

from app.api.container import Providers
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.security import AuthenticatedUser
from app.integrations.otp_delivery import (
    SimulatedInbox,
    SimulatedOtpDelivery,
    UnavailableLiveOtpDelivery,
)
from app.integrations.storage_provider import UnconfiguredStorageProvider
from app.modules.auth.phone_service import PhoneVerificationService
from tests.flows.conftest import PASSWORD, Harness

CSRF = {"X-Chikka-CSRF": "1"}


def _providers(harness: Harness) -> Providers:
    providers: Providers = harness.client.app.state.providers  # type: ignore[attr-defined]
    return providers


def _number() -> str:
    return f"+63917{uuid.uuid4().int % 10_000_000:07d}"


# -- auth provider outages -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("operation", "call"),
    [
        ("signup", lambda h: h.register(h.email())),
        (
            "resend",
            lambda h: h.client.post("/api/v1/auth/resend-verification", json={"email": h.email()}),
        ),
        (
            "recover",
            lambda h: h.client.post("/api/v1/auth/reset-password", json={"email": h.email()}),
        ),
        (
            "verify",
            lambda h: h.client.post("/api/v1/auth/verify-email", json={"token_hash": "a" * 20}),
        ),
    ],
)
def test_outages_are_503_with_a_readable_message(
    harness: Harness, operation: str, call: object
) -> None:
    harness.fake.fail_next.add(operation)
    response = call(harness)  # type: ignore[operator]
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_unavailable"
    assert "unexpected_failure" not in response.text


def test_refresh_outage_is_503(harness: Harness) -> None:
    harness.signed_up_user()
    harness.fake.fail_next.add("token")
    assert harness.client.post("/api/v1/auth/refresh", headers=CSRF).status_code == 503


def test_logout_still_revokes_when_the_provider_is_down(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    harness.fake.fail_next.add("logout")
    assert harness.client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert harness.client.get("/api/v1/users/me", headers=headers).status_code == 401


def test_reset_confirm_outage_while_setting_password(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    harness.client.post("/api/v1/auth/reset-password", json={"email": email})
    token_hash = harness.fake.last_email(email, "recovery").token_hash
    harness.fake.fail_next.add("user")
    response = harness.client.post(
        "/api/v1/auth/reset-password/confirm",
        json={
            "token_hash": token_hash,
            "new_password": "Brand-New-Pass-2",
            "confirm_password": "Brand-New-Pass-2",
        },
    )
    assert response.status_code == 503


def test_reusing_the_current_password_on_reset_is_rejected(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    harness.client.post("/api/v1/auth/reset-password", json={"email": email})
    token_hash = harness.fake.last_email(email, "recovery").token_hash
    response = harness.client.post(
        "/api/v1/auth/reset-password/confirm",
        json={"token_hash": token_hash, "new_password": PASSWORD, "confirm_password": PASSWORD},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "weak_password"


def test_reauthentication_outage_changes_nothing(harness: Harness) -> None:
    _, headers = harness.onboarded_user()
    harness.fake.fail_next.add("token")
    response = harness.client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": PASSWORD, "confirmation": "DELETE"},
        headers=headers,
    )
    assert response.status_code == 503
    assert harness.client.get("/api/v1/users/me", headers=headers).status_code == 200


def test_reauthentication_locks_after_repeated_wrong_passwords(harness: Harness) -> None:
    _, headers = harness.onboarded_user()
    body = {"password": "Wrong-Pass-1", "confirmation": "DELETE"}
    for _ in range(5):
        assert (
            harness.client.request(
                "DELETE", "/api/v1/users/me", json=body, headers=headers
            ).status_code
            == 403
        )
    locked = harness.client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": PASSWORD, "confirmation": "DELETE"},
        headers=headers,
    )
    assert locked.status_code == 429


# -- suspended accounts --------------------------------------------------------------------


def test_suspended_accounts_cannot_sign_in_or_use_tokens(harness: Harness) -> None:
    email, headers = harness.signed_up_user()
    user_id = harness.user_id(headers)
    harness.sql(
        "update public.profiles set status = 'suspended', suspended_at = now() where id = $1",
        uuid.UUID(user_id),
    )
    existing = harness.client.get("/api/v1/users/me", headers=headers)
    assert existing.status_code == 403
    assert existing.json()["error"]["code"] == "account_unavailable"

    login = harness.login(email)
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "account_unavailable"
    assert harness.client.post("/api/v1/auth/refresh", headers=CSRF).status_code == 403


# -- mobile verification edge cases --------------------------------------------------------


def test_resend_cooldown_and_expired_codes(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    number = _number()
    harness.client.post("/api/v1/users/me/phone", json={"phone_number": number}, headers=headers)
    again = harness.client.post(
        "/api/v1/users/me/phone", json={"phone_number": number}, headers=headers
    )
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "resend_cooldown"

    harness.sql(
        "update public.phone_numbers"
        " set otp_expires_at = now() - interval '1 second' where e164 = $1",
        number,
    )
    expired = harness.client.post(
        "/api/v1/users/me/phone/verify",
        json={"phone_number": number, "code": "123456"},
        headers=headers,
    )
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "otp_expired"

    harness.sql(
        "update public.phone_numbers"
        " set last_otp_sent_at = now() - interval '2 minutes' where e164 = $1",
        number,
    )
    assert (
        harness.client.post(
            "/api/v1/users/me/phone", json={"phone_number": number}, headers=headers
        ).status_code
        == 200
    )


def test_confirming_without_requesting_a_code(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    response = harness.client.post(
        "/api/v1/users/me/phone/verify",
        json={"phone_number": _number(), "code": "123456"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "otp_not_requested"


def test_reverifying_the_same_number_is_a_conflict(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    number = _number()
    harness.client.post("/api/v1/users/me/phone", json={"phone_number": number}, headers=headers)
    code = harness.client.get("/api/v1/users/me/phone/simulated-inbox", headers=headers).json()[
        "data"
    ][0]["body"]
    harness.client.post(
        "/api/v1/users/me/phone/verify",
        json={"phone_number": number, "code": code.split("code is ")[1][:6]},
        headers=headers,
    )
    again = harness.client.post(
        "/api/v1/users/me/phone", json={"phone_number": number}, headers=headers
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "already_verified"


def test_removing_when_no_number_is_verified(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    response = harness.client.request(
        "DELETE", "/api/v1/users/me/phone", json={"password": PASSWORD}, headers=headers
    )
    assert response.status_code == 404


def test_live_mode_without_sms_provider_fails_loudly_and_stores_no_code(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    _providers(harness).otp = UnavailableLiveOtpDelivery()
    number = _number()
    response = harness.client.post(
        "/api/v1/users/me/phone", json={"phone_number": number}, headers=headers
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "otp_delivery_unavailable"
    assert (
        harness.sql("select count(*) as n from public.phone_numbers where e164 = $1", number)[0][
            "n"
        ]
        == 0
    )
    # Live mode never exposes the simulated inbox.
    assert (
        harness.client.get("/api/v1/users/me/phone/simulated-inbox", headers=headers).status_code
        == 404
    )


async def test_simulated_inbox_is_never_served_in_production() -> None:
    service = PhoneVerificationService(
        settings=Settings(_env_file=None, app_env="production", app_secret_key="k" * 32),  # type: ignore[call-arg, arg-type]
        database=None,  # type: ignore[arg-type]
        delivery=SimulatedOtpDelivery(SimulatedInbox()),
        inbox=SimulatedInbox(),
        limiter=None,  # type: ignore[arg-type]
        audit=None,  # type: ignore[arg-type]
        auth_service=None,  # type: ignore[arg-type]
    )
    user = AuthenticatedUser(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        email=None,
        role="user",
        status="active",
        onboarded=True,
    )
    with pytest.raises(NotFoundError):
        service.simulated_inbox(user)


# -- storage outage ------------------------------------------------------------------------


def test_storage_outage_keeps_the_old_photo(harness: Harness) -> None:
    import io

    from PIL import Image

    _, headers = harness.signed_up_user()
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20)).save(buffer, format="PNG")
    assert (
        harness.client.post(
            "/api/v1/users/me/avatar",
            files={"avatar": ("a.png", buffer.getvalue(), "image/png")},
            headers=headers,
        ).status_code
        == 200
    )
    before = harness.profile(harness.user_id(headers))["avatar_path"]

    _providers(harness).storage = UnconfiguredStorageProvider()
    failed = harness.client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("a.png", buffer.getvalue(), "image/png")},
        headers=headers,
    )
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "storage_unavailable"
    assert harness.profile(harness.user_id(headers))["avatar_path"] == before
    # The profile still loads; the photo URL falls back to none.
    me = harness.client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["avatar_url"] is None


def test_database_unavailable_fails_closed(harness: Harness) -> None:
    app = harness.client.app
    database = app.state.database  # type: ignore[attr-defined]
    app.state.database = None  # type: ignore[attr-defined]
    try:
        assert harness.login(harness.email()).status_code == 503
    finally:
        app.state.database = database  # type: ignore[attr-defined]


def test_profile_update_is_rate_limited(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    statuses = [
        harness.client.patch("/api/v1/users/me", json={"bio": "hello"}, headers=headers).status_code
        for _ in range(61)
    ]
    assert statuses[:60] == [200] * 60
    assert statuses[60] == 429
