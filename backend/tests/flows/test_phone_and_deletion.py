import uuid

import pytest

from tests.flows.conftest import PASSWORD, Harness

# Fictional numbers in a valid range; never sent anywhere (simulation mode).
NUMBER_A = "+639171230001"
NUMBER_B = "+639171230002"


def _code(harness: Harness, headers: dict[str, str]) -> str:
    inbox = harness.client.get("/api/v1/users/me/phone/simulated-inbox", headers=headers)
    assert inbox.status_code == 200
    message = inbox.json()["data"][0]
    assert message["label"] == "SIMULATED"
    return str(message["body"].split("code is ")[1][:6])


def _verify(
    harness: Harness, headers: dict[str, str], number: str, password: str | None = None
) -> None:
    body: dict[str, str] = {"phone_number": number}
    if password:
        body["password"] = password
    start = harness.client.post("/api/v1/users/me/phone", json=body, headers=headers)
    assert start.status_code == 200, start.text
    confirm = harness.client.post(
        "/api/v1/users/me/phone/verify",
        json={"phone_number": number, "code": _code(harness, headers)},
        headers=headers,
    )
    assert confirm.status_code == 200, confirm.text


@pytest.fixture
def number() -> str:
    # Unique per test so the one-account-per-number rule does not couple tests.
    return f"+63917{uuid.uuid4().int % 10_000_000:07d}"


# -- mobile verification -------------------------------------------------------------------


def test_phone_verification_in_simulation_mode(harness: Harness, number: str) -> None:
    _, headers = harness.signed_up_user()
    start = harness.client.post(
        "/api/v1/users/me/phone", json={"phone_number": number}, headers=headers
    )
    assert start.status_code == 200
    data = start.json()["data"]
    assert data["verification_mode"] == "simulated"
    assert data["masked"] == f"+63****{number[-4:]}"
    assert data["expires_in"] == 600

    stored = harness.sql("select otp_hash from public.phone_numbers where e164 = $1", number)[0][
        "otp_hash"
    ]
    code = _code(harness, headers)
    assert code not in stored

    confirm = harness.client.post(
        "/api/v1/users/me/phone/verify",
        json={"phone_number": number, "code": code},
        headers=headers,
    )
    assert confirm.status_code == 200
    assert confirm.json()["data"]["verified"] is True
    assert confirm.json()["data"]["verification_mode"] == "simulated"
    profile = harness.client.get("/api/v1/users/me", headers=headers).json()["data"]
    assert profile["phone"]["masked"].endswith(number[-4:])
    assert (
        harness.client.get("/api/v1/users/me/phone/simulated-inbox", headers=headers).json()["data"]
        == []
    )


def test_email_and_mobile_verification_are_separate(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    status = harness.client.get("/api/v1/users/me/phone", headers=headers).json()["data"]
    assert status["verified"] is False
    assert (
        harness.client.get("/api/v1/users/me", headers=headers).json()["data"]["email_verified"]
        is True
    )


def test_wrong_codes_are_counted_and_invalidate_after_five(harness: Harness, number: str) -> None:
    _, headers = harness.signed_up_user()
    harness.client.post("/api/v1/users/me/phone", json={"phone_number": number}, headers=headers)
    real = _code(harness, headers)
    wrong = "000000" if real != "000000" else "111111"
    for remaining in (4, 3, 2, 1):
        response = harness.client.post(
            "/api/v1/users/me/phone/verify",
            json={"phone_number": number, "code": wrong},
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["details"]["attempts_remaining"] == remaining
    locked = harness.client.post(
        "/api/v1/users/me/phone/verify",
        json={"phone_number": number, "code": wrong},
        headers=headers,
    )
    assert locked.json()["error"]["code"] == "otp_locked"
    after = harness.client.post(
        "/api/v1/users/me/phone/verify",
        json={"phone_number": number, "code": real},
        headers=headers,
    )
    assert after.status_code == 400


def test_number_verified_elsewhere_gets_a_neutral_refusal(harness: Harness, number: str) -> None:
    _, alice = harness.signed_up_user()
    _verify(harness, alice, number)
    _, bob = harness.signed_up_user()
    response = harness.client.post(
        "/api/v1/users/me/phone", json={"phone_number": number}, headers=bob
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "phone_unavailable"
    assert "another account" not in response.json()["error"]["message"].lower()


def test_invalid_numbers_are_rejected(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    for raw in ("09171234567", "+1234", "+63abc"):
        assert (
            harness.client.post(
                "/api/v1/users/me/phone", json={"phone_number": raw}, headers=headers
            ).status_code
            == 422
        )


def test_code_sends_are_limited_to_three_per_half_hour(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    for index in range(3):
        number = f"+63917{uuid.uuid4().int % 10_000_000:07d}"
        assert (
            harness.client.post(
                "/api/v1/users/me/phone", json={"phone_number": number}, headers=headers
            ).status_code
            == 200
        ), index
    limited = harness.client.post(
        "/api/v1/users/me/phone", json={"phone_number": NUMBER_A}, headers=headers
    )
    assert limited.status_code == 429


def test_changing_and_removing_a_number_needs_the_password(harness: Harness, number: str) -> None:
    _, headers = harness.signed_up_user()
    _verify(harness, headers, number)
    replacement = f"+63918{uuid.uuid4().int % 10_000_000:07d}"

    no_password = harness.client.post(
        "/api/v1/users/me/phone", json={"phone_number": replacement}, headers=headers
    )
    assert no_password.status_code == 403
    assert no_password.json()["error"]["code"] == "reauthentication_required"

    _verify(harness, headers, replacement, password=PASSWORD)
    status = harness.client.get("/api/v1/users/me/phone", headers=headers).json()["data"]
    assert status["masked"].endswith(replacement[-4:])
    old = harness.sql("select status from public.phone_numbers where e164 = $1", number)[0]
    assert old["status"] == "released"

    wrong = harness.client.request(
        "DELETE", "/api/v1/users/me/phone", json={"password": "Wrong-Pass-1"}, headers=headers
    )
    assert wrong.status_code == 403
    assert (
        harness.client.request(
            "DELETE", "/api/v1/users/me/phone", json={"password": PASSWORD}, headers=headers
        ).status_code
        == 204
    )
    assert (
        harness.client.get("/api/v1/users/me/phone", headers=headers).json()["data"]["verified"]
        is False
    )


def test_unverified_accounts_cannot_use_phone_verification(harness: Harness) -> None:
    email = harness.email()
    harness.register(email)
    # An unverified user has no session at all; the endpoint requires one.
    assert (
        harness.client.post("/api/v1/users/me/phone", json={"phone_number": NUMBER_B}).status_code
        == 401
    )


# -- account deletion ----------------------------------------------------------------------


def test_account_deletion_requires_password_and_confirmation(harness: Harness) -> None:
    _, headers = harness.onboarded_user()
    wrong_password = harness.client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": "Wrong-Pass-1", "confirmation": "DELETE"},
        headers=headers,
    )
    assert wrong_password.status_code == 403
    assert wrong_password.json()["error"]["code"] == "reauthentication_failed"
    no_phrase = harness.client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": PASSWORD, "confirmation": "yes"},
        headers=headers,
    )
    assert no_phrase.status_code == 422
    assert harness.client.get("/api/v1/users/me", headers=headers).status_code == 200


def test_account_deletion_erases_profile_and_blocks_access(harness: Harness, number: str) -> None:
    email, headers = harness.onboarded_user()
    user_id = harness.user_id(headers)
    _verify(harness, headers, number)
    harness.client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("a.png", _tiny_png(), "image/png")},
        headers=headers,
    )
    other_device = {
        "Authorization": f"Bearer {harness.login(email).json()['data']['access_token']}"
    }

    response = harness.client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": PASSWORD, "confirmation": "DELETE"},
        headers=headers,
    )
    assert response.status_code == 202, response.text

    profile = harness.profile(user_id)
    assert profile["status"] == "deleted"
    assert profile["deleted_at"] is not None
    assert profile["username"] is None
    assert profile["display_name"] == "Deleted user"
    assert profile["avatar_path"] is None and profile["bio"] is None
    phones = harness.sql(
        "select status from public.phone_numbers where user_id = $1", uuid.UUID(user_id)
    )
    assert {p["status"] for p in phones} == {"released"}
    assert harness.fake.objects == {}
    # Consent history and audit rows are retained.
    assert (
        harness.sql(
            "select count(*) as n from public.user_consents where user_id = $1", uuid.UUID(user_id)
        )[0]["n"]
        == 2
    )
    assert (
        harness.sql(
            "select count(*) as n from public.audit_logs"
            " where action = 'account.deleted' and actor_id = $1",
            uuid.UUID(user_id),
        )[0]["n"]
        == 1
    )

    for device in (headers, other_device):
        assert harness.client.get("/api/v1/users/me", headers=device).status_code in (401, 403)
    assert harness.login(email).status_code == 401
    assert harness.fake.user_by_id(user_id).email.startswith("deleted-")


def test_deletion_is_atomic_when_auth_provider_fails(harness: Harness) -> None:
    _, headers = harness.onboarded_user()
    user_id = harness.user_id(headers)
    harness.fake.fail_next.add(user_id)  # the admin update path ends with the user id
    response = harness.client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": PASSWORD, "confirmation": "DELETE"},
        headers=headers,
    )
    assert response.status_code == 503
    assert harness.profile(user_id)["status"] == "active"


def _tiny_png() -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (10, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


# -- logging hygiene -----------------------------------------------------------------------


def test_logs_never_contain_passwords_codes_or_tokens(
    capsys: pytest.CaptureFixture[str], harness: Harness, number: str
) -> None:
    # capsys is requested first so the app's log handler binds to the captured stream.
    secret_password = "Unique-Secret-Pass-77"
    email = harness.email()
    harness.register(email, password=secret_password)
    harness.verify(email)
    login = harness.login(email, secret_password)
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    harness.login(email, "Wrong-Pass-1")
    harness.client.post("/api/v1/users/me/phone", json={"phone_number": number}, headers=headers)
    code = _code(harness, headers)

    output = capsys.readouterr()
    logs = output.out + output.err
    assert "request completed" in logs  # logging was captured
    for secret in (secret_password, "Wrong-Pass-1", token, code, number):
        assert secret not in logs
