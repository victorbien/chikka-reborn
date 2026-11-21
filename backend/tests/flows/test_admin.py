"""Administration dashboard (Module J) against a real database.

The shared database persists between tests, so totals are compared as before/after deltas and
rows are found by the ids this test created.
"""

import uuid
from typing import Any

from tests.flows.conftest import Harness
from tests.flows.test_sms import NUMBER, admin_user, ready_to_send, send, sms_user

API = "/api/v1/admin"


def get(harness: Harness, headers: dict[str, str], path: str, **params: Any) -> Any:
    return harness.client.get(f"{API}{path}", headers=headers, params=params)


def audit_rows(harness: Harness, action: str, target: str | None = None) -> list[Any]:
    if target is None:
        return harness.sql(
            "select * from public.audit_logs where action = $1 order by created_at", action
        )
    return harness.sql(
        "select * from public.audit_logs where action = $1 and target_id = $2 order by created_at",
        action,
        target,
    )


def dashboard(harness: Harness, headers: dict[str, str]) -> dict[str, Any]:
    response = get(harness, headers, "/dashboard")
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


# -- authorisation and isolation --------------------------------------------------------------


def test_ordinary_users_are_refused_and_the_attempt_is_audited(harness: Harness) -> None:
    headers, user_id = sms_user(harness)
    _, other_id = sms_user(harness)
    before = len(audit_rows(harness, "admin.access_denied"))

    for path in ("/dashboard", "/users", f"/users/{other_id}", "/sms/messages", "/audit-logs"):
        assert get(harness, headers, path).status_code == 403
    restrict = harness.client.post(
        f"{API}/users/{other_id}/restrict", json={"reason_code": "spam"}, headers=headers
    )
    assert restrict.status_code == 403

    assert harness.profile(other_id)["status"] == "active"
    rows = audit_rows(harness, "admin.access_denied")
    assert len(rows) - before == 6
    assert all(r["outcome"] == "denied" for r in rows[before:])
    assert str(rows[-1]["actor_id"]) == user_id
    assert rows[-1]["category"] == "security"


def test_a_user_promoted_in_the_database_gains_access_and_a_demoted_one_loses_it(
    harness: Harness,
) -> None:
    headers, user_id = sms_user(harness)
    assert get(harness, headers, "/dashboard").status_code == 403
    harness.sql("update public.profiles set role = 'admin' where id = $1", uuid.UUID(user_id))
    assert get(harness, headers, "/dashboard").status_code == 200
    harness.sql("update public.profiles set role = 'user' where id = $1", uuid.UUID(user_id))
    assert get(harness, headers, "/dashboard").status_code == 403


def test_a_suspended_administrator_loses_access(harness: Harness) -> None:
    headers, user_id = admin_user(harness)
    assert get(harness, headers, "/dashboard").status_code == 200
    harness.sql(
        "update public.profiles set status = 'suspended', suspended_at = now() where id = $1",
        uuid.UUID(user_id),
    )
    assert get(harness, headers, "/dashboard").status_code == 403


# -- dashboard --------------------------------------------------------------------------------


def test_dashboard_counts_come_from_real_rows_and_keep_simulation_apart(
    harness: Harness,
) -> None:
    admin_headers, _ = admin_user(harness)
    before = dashboard(harness, admin_headers)

    sender, _ = ready_to_send(harness)
    assert send(harness, sender).status_code == 202
    for _ in range(3):
        harness.clock.advance(3)
        harness.run_worker()

    after = dashboard(harness, admin_headers)
    assert after["users"]["total_registered"] - before["users"]["total_registered"] == 1
    assert after["conversations"]["sms"] - before["conversations"]["sms"] == 1
    simulated_before, simulated_after = before["sms"]["simulated"], after["sms"]["simulated"]
    assert simulated_after["sent"] - simulated_before["sent"] == 1
    assert simulated_after["delivered"] - simulated_before["delivered"] == 1
    assert simulated_after["delivery_success_rate"] is not None
    assert after["sms"]["live"] == before["sms"]["live"]
    demo = {c["ledger_type"]: c for c in after["credits"]}
    assert "demo" in demo
    assert demo["demo"]["units_deducted"] >= 1


def test_dashboard_counts_ai_requests_without_exposing_content(harness: Harness) -> None:
    admin_headers, _ = admin_user(harness)
    _, user_id = sms_user(harness)
    before = dashboard(harness, admin_headers)["ai"]
    harness.sql(
        "insert into public.ai_assistance_logs (user_id, feature, model_id, outcome,"
        " input_tokens, output_tokens, latency_ms, input_text, output_text, content_expires_at)"
        " values ($1, 'rewrite', 'test-model', 'success', 120, 40, 250,"
        " 'PRIVATE-DRAFT-TEXT', 'PRIVATE-REWRITE', now() + interval '30 days'),"
        " ($1, 'translate', 'test-model', 'timeout', 10, 0, 15000, null, null, null)",
        uuid.UUID(user_id),
    )
    after = dashboard(harness, admin_headers)["ai"]
    assert after["total_requests"] - before["total_requests"] == 2
    assert after["failed_requests"] - before["failed_requests"] == 1
    assert after["input_tokens"] - before["input_tokens"] == 130

    metrics = get(harness, admin_headers, "/ai/metrics", window_days=7)
    assert metrics.status_code == 200
    data = metrics.json()["data"]
    features = {f["feature"]: f for f in data["features"]}
    assert features["rewrite"]["requests"] >= 1
    assert any(e["outcome"] == "timeout" for e in data["errors"])
    assert data["estimated_cost_usd"] is None  # no prices configured: nothing is guessed
    for text in (metrics.text, get(harness, admin_headers, f"/users/{user_id}").text):
        assert "PRIVATE-DRAFT-TEXT" not in text
        assert "PRIVATE-REWRITE" not in text


# -- users ------------------------------------------------------------------------------------


def test_user_search_details_and_masking(harness: Harness) -> None:
    admin_headers, admin_id = admin_user(harness)
    email, member = harness.onboarded_user()
    member_id = harness.user_id(member)
    username = harness.profile(member_id)["username"]

    found = get(harness, admin_headers, "/users", q=username)
    assert found.status_code == 200
    items = found.json()["data"]
    assert [i["id"] for i in items] == [member_id]
    assert found.json()["pagination"]["total"] == 1
    assert email not in found.text
    assert items[0]["masked_email"].endswith("@example.com")

    # Searching by the full address works, and the address is still not returned.
    by_email = get(harness, admin_headers, "/users", q=email)
    assert [i["id"] for i in by_email.json()["data"]] == [member_id]
    assert email not in by_email.text

    # Wildcards in the search are literal characters, not patterns.
    assert get(harness, admin_headers, "/users", q="%").json()["data"] == []

    admins = get(harness, admin_headers, "/users", role="admin").json()["data"]
    assert admin_id in {a["id"] for a in admins}

    detail = get(harness, admin_headers, f"/users/{member_id}")
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["status"] == "active"
    assert body["activity"]["conversations"] == 0
    assert email not in detail.text
    viewed = audit_rows(harness, "admin.user_viewed", member_id)
    assert len(viewed) == 1
    assert str(viewed[0]["actor_id"]) == admin_id

    assert get(harness, admin_headers, f"/users/{uuid.uuid4()}").status_code == 404


def test_restricting_an_account_ends_its_sessions_and_is_audited(harness: Harness) -> None:
    admin_headers, admin_id = admin_user(harness)
    email, member = harness.onboarded_user()
    member_id = harness.user_id(member)
    assert harness.client.get("/api/v1/users/me", headers=member).status_code == 200

    response = harness.client.post(
        f"{API}/users/{member_id}/restrict", json={"reason_code": "abuse"}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "suspended"
    assert harness.profile(member_id)["status"] == "suspended"
    assert harness.client.get("/api/v1/users/me", headers=member).status_code in (401, 403)
    assert harness.login(email).status_code in (401, 403)

    rows = audit_rows(harness, "admin.user_restricted", member_id)
    assert len(rows) == 1
    assert str(rows[0]["actor_id"]) == admin_id
    assert rows[0]["outcome"] == "success"
    assert rows[0]["metadata"] is not None

    reinstated = harness.client.post(f"{API}/users/{member_id}/reinstate", headers=admin_headers)
    assert reinstated.status_code == 200, reinstated.text
    assert harness.profile(member_id)["status"] == "active"
    assert harness.profile(member_id)["suspended_at"] is None
    assert harness.login(email).status_code == 200
    assert len(audit_rows(harness, "admin.user_reinstated", member_id)) == 1


def test_restriction_rules_protect_administrators_and_enforce_state(harness: Harness) -> None:
    admin_headers, admin_id = admin_user(harness)
    _, other_admin_id = admin_user(harness)
    _, member = harness.onboarded_user()
    member_id = harness.user_id(member)

    def restrict(target: str) -> Any:
        return harness.client.post(
            f"{API}/users/{target}/restrict", json={"reason_code": "spam"}, headers=admin_headers
        )

    own = restrict(admin_id)
    assert own.status_code == 409
    assert own.json()["error"]["code"] == "cannot_restrict_self"
    other = restrict(other_admin_id)
    assert other.status_code == 409
    assert other.json()["error"]["code"] == "cannot_restrict_administrator"
    assert restrict(str(uuid.uuid4())).status_code == 404
    assert harness.profile(admin_id)["status"] == "active"
    assert harness.profile(other_admin_id)["status"] == "active"

    refused = audit_rows(harness, "admin.user_restrict_refused", admin_id)
    assert len(refused) == 1
    assert refused[0]["outcome"] == "denied"

    not_suspended = harness.client.post(f"{API}/users/{member_id}/reinstate", headers=admin_headers)
    assert not_suspended.status_code == 409
    assert not_suspended.json()["error"]["code"] == "account_not_suspended"

    invalid = harness.client.post(
        f"{API}/users/{member_id}/restrict",
        json={"reason_code": "because", "role": "admin"},
        headers=admin_headers,
    )
    assert invalid.status_code == 422
    assert harness.profile(member_id)["status"] == "active"


# -- SMS monitoring ---------------------------------------------------------------------------


def test_sms_lists_show_attempts_and_provider_ids_without_bodies_or_full_numbers(
    harness: Harness,
) -> None:
    admin_headers, admin_id = admin_user(harness)
    sender, sender_id = ready_to_send(harness)
    body = "PRIVATE-SMS-BODY kumusta"
    sent = send(harness, sender, body=body).json()["data"]
    for _ in range(3):
        harness.clock.advance(3)
        harness.run_worker()

    listing = get(harness, admin_headers, "/sms/messages", direction="outbound", is_simulated=True)
    assert listing.status_code == 200
    row = next(r for r in listing.json()["data"] if r["id"] == sent["id"])
    assert row["status"] == "delivered"
    assert row["is_simulated"] is True
    assert row["provider_message_id"]
    assert row["user_id"] == sender_id
    assert row["masked_phone"] == "+12****0142"
    assert NUMBER not in listing.text
    assert "PRIVATE-SMS-BODY" not in listing.text

    detail = get(harness, admin_headers, f"/sms/messages/{sent['id']}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["attempts_history"][0]["attempt_number"] == 1
    statuses = [e["normalised_status"] for e in data["attempts_history"][0]["events"]]
    assert "delivered" in statuses
    assert "PRIVATE-SMS-BODY" not in detail.text
    assert NUMBER not in detail.text
    assert len(audit_rows(harness, "admin.sms_message_viewed", sent["id"])) == 1
    assert str(audit_rows(harness, "admin.sms_message_viewed", sent["id"])[0]["actor_id"]) == (
        admin_id
    )

    inbound = get(harness, admin_headers, "/sms/messages", direction="inbound")
    assert inbound.status_code == 200
    assert all(r["direction"] == "inbound" for r in inbound.json()["data"])
    assert get(harness, admin_headers, f"/sms/messages/{uuid.uuid4()}").status_code == 404
    assert get(harness, admin_headers, "/sms/messages", direction="sideways").status_code == 422


def test_failed_messages_show_the_failure_reason_and_retry_history(harness: Harness) -> None:
    admin_headers, _ = admin_user(harness)
    always_transient = "+12025550104"  # mock scenario: transient error on every attempt
    sender, _ = ready_to_send(harness, always_transient)
    sent = send(harness, sender, to=always_transient).json()["data"]
    for _ in range(12):
        harness.clock.advance(400)
        harness.run_worker()

    detail = get(harness, admin_headers, f"/sms/messages/{sent['id']}").json()["data"]
    assert detail["status"] == "failed"
    assert detail["failure_code"] == "retries_exhausted"
    assert detail["failure_class"] == "transient"
    assert any(a["failure_code"] == "SIM-TRANSIENT" for a in detail["attempts_history"])
    assert detail["failure_reason"]
    assert detail["attempts"] == len(detail["attempts_history"]) > 1
    assert [a["attempt_number"] for a in detail["attempts_history"]] == list(
        range(1, detail["attempts"] + 1)
    )
    assert always_transient not in str(detail)

    failed = get(harness, admin_headers, "/sms/messages", status="failed", is_simulated=True)
    assert sent["id"] in {r["id"] for r in failed.json()["data"]}


# -- providers --------------------------------------------------------------------------------


def test_provider_overview_reports_mode_health_and_never_secrets(harness: Harness) -> None:
    admin_headers, _ = admin_user(harness)
    response = get(harness, admin_headers, "/providers/overview")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["health"]["mode"] == "simulation"
    assert data["health"]["running_provider"] == "mock"
    assert data["health"]["health"] in ("healthy", "degraded", "paused")
    assert data["configuration"]["sms_provider_mode"] == "mock"
    assert data["configuration"]["ai_provider_configured"] is True
    assert any(c["country_code"] == "PH" for c in data["capabilities"])
    for forbidden in ("token", "secret", "password", "api_key", "service_role"):
        assert forbidden not in response.text.lower().replace("webhook_signature", "")


def test_pausing_outbound_sms_is_reflected_in_provider_health(harness: Harness) -> None:
    admin_headers, _ = admin_user(harness)
    paused = harness.client.put(
        "/api/v1/admin/sms/outbound-paused", json={"paused": True}, headers=admin_headers
    )
    assert paused.status_code == 200
    try:
        health = get(harness, admin_headers, "/providers/overview").json()["data"]["health"]
        assert health["outbound_paused"] is True
        assert health["health"] in ("paused", "degraded")
    finally:
        harness.client.put(
            "/api/v1/admin/sms/outbound-paused", json={"paused": False}, headers=admin_headers
        )


# -- audit log --------------------------------------------------------------------------------


def test_audit_log_is_readable_filterable_and_free_of_sensitive_data(harness: Harness) -> None:
    admin_headers, admin_id = admin_user(harness)
    _, member = harness.onboarded_user()
    member_id = harness.user_id(member)
    harness.client.post(
        f"{API}/users/{member_id}/restrict", json={"reason_code": "fraud"}, headers=admin_headers
    )

    response = get(
        harness, admin_headers, "/audit-logs", action="user_restricted", actor_id=admin_id
    )
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert rows
    top = rows[0]
    assert top["action"] == "admin.user_restricted"
    assert top["actor_id"] == admin_id
    assert top["actor_role"] == "admin"
    assert top["target_type"] == "user"
    assert top["target_id"] == member_id
    assert top["outcome"] == "success"
    assert top["created_at"]
    assert "metadata" not in top

    denied = get(harness, admin_headers, "/audit-logs", outcome="denied")
    assert all(r["outcome"] == "denied" for r in denied.json()["data"])
    assert get(harness, admin_headers, "/audit-logs", outcome="maybe").status_code == 422
    assert get(harness, admin_headers, "/audit-logs", page_size=1000).status_code == 422


def test_audit_log_cannot_be_read_or_changed_by_other_users(harness: Harness) -> None:
    member_headers, _ = sms_user(harness)
    assert get(harness, member_headers, "/audit-logs").status_code == 403
    for method in ("put", "patch", "delete"):
        response = getattr(harness.client, method)(f"{API}/audit-logs", headers=member_headers)
        assert response.status_code in (403, 404, 405)
