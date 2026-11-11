from tests.flows.conftest import PASSWORD, Harness

CSRF = {"X-Chikka-CSRF": "1"}


def _body(response: object) -> dict[str, object]:
    data = response.json()  # type: ignore[attr-defined]
    return {k: v for k, v in data.items() if k != "request_id"}


# -- login ---------------------------------------------------------------------------------


def test_successful_login_issues_memory_token_and_httponly_refresh_cookie(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    response = harness.login(email)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert set(data) == {"access_token", "token_type", "expires_in"}
    assert "HttpOnly" in response.headers["set-cookie"]


def test_login_email_is_case_insensitive(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    assert harness.login(email.upper()).status_code == 200


def test_wrong_password_and_unknown_email_get_identical_answers(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    wrong_password = harness.login(email, "Wrong-Pass-1")
    unknown_email = harness.login(harness.email(), "Wrong-Pass-1")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert _body(wrong_password) == _body(unknown_email)
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"


def test_five_failures_lock_the_account_without_revealing_it_exists(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    unknown = harness.email()
    for target in (email, unknown):
        for _ in range(5):
            assert harness.login(target, "Wrong-Pass-1").status_code == 401
        locked = harness.login(target, "Wrong-Pass-1")
        assert locked.status_code == 429
        assert int(locked.headers["Retry-After"]) > 0

    # Even the right password is refused while locked.
    assert harness.login(email, PASSWORD).status_code == 429
    lockouts = harness.sql(
        "select count(*) as n from public.audit_logs where action = 'auth.lockout'"
    )
    assert lockouts[0]["n"] >= 2


def test_successful_login_resets_the_failure_counter(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    for _ in range(4):
        harness.login(email, "Wrong-Pass-1")
    assert harness.login(email).status_code == 200
    for _ in range(4):
        assert harness.login(email, "Wrong-Pass-1").status_code == 401
    assert harness.login(email).status_code == 200


# -- refresh and logout --------------------------------------------------------------------


def test_refresh_requires_the_csrf_header_and_rotates(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    harness.login(email)

    no_header = harness.client.post("/api/v1/auth/refresh")
    assert no_header.status_code == 403
    assert no_header.json()["error"]["code"] == "csrf_required"

    refreshed = harness.client.post("/api/v1/auth/refresh", headers=CSRF)
    assert refreshed.status_code == 200
    token = refreshed.json()["data"]["access_token"]
    assert (
        harness.client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )


def test_refresh_without_cookie_is_401(harness: Harness) -> None:
    harness.client.cookies.clear()
    response = harness.client.post("/api/v1/auth/refresh", headers=CSRF)
    assert response.status_code == 401


def test_logout_revokes_the_token_immediately(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    assert harness.client.post("/api/v1/auth/logout", headers=headers).status_code == 204

    after = harness.client.get("/api/v1/users/me", headers=headers)
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "session_revoked"
    assert harness.client.post("/api/v1/auth/refresh", headers=CSRF).status_code == 401


def test_global_logout_ends_every_device(harness: Harness) -> None:
    email, first = harness.signed_up_user()
    second = {"Authorization": f"Bearer {harness.login(email).json()['data']['access_token']}"}
    response = harness.client.post("/api/v1/auth/logout", json={"scope": "global"}, headers=second)
    assert response.status_code == 204
    assert harness.client.get("/api/v1/users/me", headers=first).status_code == 401


# -- session management --------------------------------------------------------------------


def test_list_and_revoke_sessions(harness: Harness) -> None:
    email, first = harness.signed_up_user()
    assert harness.login(email).status_code == 200  # a second device

    sessions = harness.client.get("/api/v1/auth/sessions", headers=first).json()["data"]
    assert len(sessions) >= 2
    current = [s for s in sessions if s["current"]]
    assert len(current) == 1
    assert sessions[0]["device"] == "Chrome on Windows"
    assert sessions[0]["ip_prefix"] == "203.0.113.0/24"

    own = harness.client.delete(f"/api/v1/auth/sessions/{current[0]['id']}", headers=first)
    assert own.status_code == 400

    other = next(s for s in sessions if not s["current"])
    assert (
        harness.client.delete(f"/api/v1/auth/sessions/{other['id']}", headers=first).status_code
        == 204
    )
    assert harness.client.get("/api/v1/users/me", headers=first).status_code == 200


def test_revoke_other_sessions_keeps_the_current_one(harness: Harness) -> None:
    email, first = harness.signed_up_user()
    second = {"Authorization": f"Bearer {harness.login(email).json()['data']['access_token']}"}
    response = harness.client.post("/api/v1/auth/sessions/revoke-others", headers=second)
    assert response.status_code == 200
    assert harness.client.get("/api/v1/users/me", headers=first).status_code == 401
    assert harness.client.get("/api/v1/users/me", headers=second).status_code == 200


def test_cannot_revoke_another_users_session(harness: Harness) -> None:
    _, alice = harness.signed_up_user()
    _, bob = harness.signed_up_user()
    bob_session = harness.client.get("/api/v1/auth/sessions", headers=bob).json()["data"][0]["id"]
    response = harness.client.delete(f"/api/v1/auth/sessions/{bob_session}", headers=alice)
    assert response.status_code == 404
    assert harness.client.get("/api/v1/users/me", headers=bob).status_code == 200


# -- password reset ------------------------------------------------------------------------


def test_reset_request_is_neutral_for_known_and_unknown_addresses(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    known = harness.client.post("/api/v1/auth/reset-password", json={"email": email})
    unknown = harness.client.post("/api/v1/auth/reset-password", json={"email": harness.email()})
    assert known.status_code == unknown.status_code == 200
    assert _body(known) == _body(unknown)
    assert harness.fake.last_email(email, "recovery")


def test_password_reset_changes_password_and_revokes_sessions(harness: Harness) -> None:
    email, old_headers = harness.signed_up_user()
    harness.client.post("/api/v1/auth/reset-password", json={"email": email})
    token_hash = harness.fake.last_email(email, "recovery").token_hash

    response = harness.client.post(
        "/api/v1/auth/reset-password/confirm",
        json={
            "token_hash": token_hash,
            "new_password": "Brand-New-Pass-2",
            "confirm_password": "Brand-New-Pass-2",
        },
    )
    assert response.status_code == 200

    assert harness.client.get("/api/v1/users/me", headers=old_headers).status_code == 401
    assert harness.login(email, PASSWORD).status_code == 401
    assert harness.login(email, "Brand-New-Pass-2").status_code == 200

    reused = harness.client.post(
        "/api/v1/auth/reset-password/confirm",
        json={
            "token_hash": token_hash,
            "new_password": "Another-Pass-3",
            "confirm_password": "Another-Pass-3",
        },
    )
    assert reused.status_code == 400


def test_password_reset_validates_before_using_the_link(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    harness.client.post("/api/v1/auth/reset-password", json={"email": email})
    token_hash = harness.fake.last_email(email, "recovery").token_hash

    mismatch = harness.client.post(
        "/api/v1/auth/reset-password/confirm",
        json={
            "token_hash": token_hash,
            "new_password": "Brand-New-Pass-2",
            "confirm_password": "Different-Pass-2",
        },
    )
    weak = harness.client.post(
        "/api/v1/auth/reset-password/confirm",
        json={"token_hash": token_hash, "new_password": "weak", "confirm_password": "weak"},
    )
    assert mismatch.status_code == weak.status_code == 422
    # The link is still usable because validation ran first.
    ok = harness.client.post(
        "/api/v1/auth/reset-password/confirm",
        json={
            "token_hash": token_hash,
            "new_password": "Brand-New-Pass-2",
            "confirm_password": "Brand-New-Pass-2",
        },
    )
    assert ok.status_code == 200


def test_reset_requests_are_rate_limited(harness: Harness) -> None:
    for _ in range(3):
        harness.client.post("/api/v1/auth/reset-password", json={"email": harness.email()})
    limited = harness.client.post("/api/v1/auth/reset-password", json={"email": harness.email()})
    assert limited.status_code == 429


def test_auth_provider_outage_is_a_readable_503(harness: Harness) -> None:
    email, _ = harness.signed_up_user()
    harness.fake.fail_next.add("token")
    response = harness.login(email)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_unavailable"
