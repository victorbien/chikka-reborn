import uuid

from tests.flows.conftest import PASSWORD, Harness


def _without_request_id(body: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in body.items() if key != "request_id"}


def test_successful_registration_creates_pending_profile_and_consents(harness: Harness) -> None:
    email = harness.email()
    response = harness.register(email)

    assert response.status_code == 202
    assert "confirm" in response.json()["data"]["message"]
    user_id = harness.fake.users[email].id
    profile = harness.profile(user_id)
    assert profile["status"] == "pending_verification"
    assert profile["display_name"] == "Marites Santos"
    consents = harness.sql(
        "select consent_type, source from public.user_consents where user_id = $1 order by 1",
        uuid.UUID(user_id),
    )
    assert [(c["consent_type"], c["source"]) for c in consents] == [
        ("privacy", "registration"),
        ("terms", "registration"),
    ]
    assert harness.fake.last_email(email, "signup")


def test_registration_rejects_invalid_input_with_field_errors(harness: Harness) -> None:
    cases = {
        "body.email": {"email": "not-an-email"},
        "body.password": {"password": "alllowercase1"},
        "body.display_name": {"display_name": "A"},
        "body.accept_terms": {"accept_terms": False},
    }
    for field, override in cases.items():
        email = harness.email()
        body = {
            "email": email,
            "password": PASSWORD,
            "display_name": "Valid Name",
            "accept_terms": True,
            **override,
        }
        response = harness.client.post("/api/v1/auth/register", json=body)
        assert response.status_code == 422, field
        fields = [p["field"] for p in response.json()["error"]["details"]["problems"]]
        assert field in fields
        assert email not in harness.fake.users


def test_registration_rejects_unknown_fields(harness: Harness) -> None:
    response = harness.client.post(
        "/api/v1/auth/register",
        json={
            "email": harness.email(),
            "password": PASSWORD,
            "display_name": "Valid Name",
            "accept_terms": True,
            "role": "admin",
        },
    )
    assert response.status_code == 422


def test_duplicate_registration_is_indistinguishable(harness: Harness) -> None:
    email = harness.email()
    first = harness.register(email)
    emails_before = len(harness.fake.outbox)
    second = harness.register(email, password="Another-Pass-9")

    assert first.status_code == second.status_code == 202
    assert _without_request_id(first.json()) == _without_request_id(second.json())
    assert len(harness.fake.outbox) == emails_before


def test_unverified_account_cannot_sign_in(harness: Harness) -> None:
    email = harness.email()
    harness.register(email)
    response = harness.login(email)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


def test_email_verification_activates_and_signs_in(harness: Harness) -> None:
    email = harness.email()
    harness.register(email)
    response = harness.verify(email)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["token_type"] == "bearer"
    assert "refresh_token" not in data
    cookie = response.headers["set-cookie"]
    assert "chikka_refresh=" in cookie and "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie
    assert harness.profile(harness.fake.users[email].id)["status"] == "active"

    me = harness.client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["data"]["email_verified"] is True
    assert me.json()["data"]["email"] == email


def test_verification_link_is_single_use(harness: Harness) -> None:
    email = harness.email()
    harness.register(email)
    token_hash = harness.fake.last_email(email, "signup").token_hash
    assert (
        harness.client.post(
            "/api/v1/auth/verify-email", json={"token_hash": token_hash}
        ).status_code
        == 200
    )
    reused = harness.client.post("/api/v1/auth/verify-email", json={"token_hash": token_hash})
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "invalid_or_expired_link"


def test_expired_verification_link_is_rejected(harness: Harness) -> None:
    email = harness.email()
    harness.register(email)
    harness.fake.expire_tokens()
    response = harness.verify(email)
    assert response.status_code == 400
    assert harness.profile(harness.fake.users[email].id)["status"] == "pending_verification"


def test_resend_invalidates_the_previous_link_and_is_neutral(harness: Harness) -> None:
    email = harness.email()
    harness.register(email)
    old = harness.fake.last_email(email, "signup").token_hash

    known = harness.client.post("/api/v1/auth/resend-verification", json={"email": email})
    unknown = harness.client.post(
        "/api/v1/auth/resend-verification", json={"email": harness.email()}
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json()["data"] == unknown.json()["data"]

    assert (
        harness.client.post("/api/v1/auth/verify-email", json={"token_hash": old}).status_code
        == 400
    )
    assert harness.verify(email).status_code == 200


def test_resend_is_rate_limited(harness: Harness) -> None:
    email = harness.email()
    for _ in range(3):
        assert (
            harness.client.post(
                "/api/v1/auth/resend-verification", json={"email": email}
            ).status_code
            == 200
        )
    limited = harness.client.post("/api/v1/auth/resend-verification", json={"email": email})
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
