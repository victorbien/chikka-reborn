"""Internet-to-SMS and SMS-to-internet, end to end, in simulation mode.

Nothing here reaches a real provider: MockSmsProvider produces signed callbacks that go through
the real webhook path. Time is a shared FakeClock; the worker is run explicitly.
"""

import uuid
from typing import Any

import httpx
import pytest

from tests.flows.conftest import Harness

NUMBER = "+12025550142"  # fictional (NANP 555-01xx), default scenario: delivered
PLATFORM = "+12025550190"


def sms_user(harness: Harness) -> tuple[dict[str, str], str]:
    """An onboarded user with a verified (simulated) mobile number."""
    _, headers = harness.onboarded_user()
    user_id = harness.user_id(headers)
    harness.sql(
        "insert into public.phone_numbers (user_id, e164, country_code, verification_mode,"
        " status, verified_at) values ($1, $2, 'PH', 'simulated', 'verified', now())",
        uuid.UUID(user_id),
        f"+63917{uuid.uuid4().int % 10_000_000:07d}",
    )
    return headers, user_id


def consent(harness: Harness, headers: dict[str, str], to: str, decision: str = "granted") -> None:
    response = harness.client.put(
        "/api/v1/sms/consents", json={"to": to, "decision": decision}, headers=headers
    )
    assert response.status_code == 200, response.text


def send(
    harness: Harness,
    headers: dict[str, str],
    to: str = NUMBER,
    body: str = "Kumusta ka, Nanay?",
    key: str | None = None,
    **extra: Any,
) -> httpx.Response:
    return harness.client.post(
        "/api/v1/sms/messages",
        json={"to": to, "body": body, "confirmed": True, **extra},
        headers={**headers, "Idempotency-Key": key or str(uuid.uuid4())},
    )


def message(harness: Harness, headers: dict[str, str], message_id: str) -> dict[str, Any]:
    response = harness.client.get(f"/api/v1/sms/messages/{message_id}", headers=headers)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]["message"]
    return data


def ready_to_send(harness: Harness, to: str = NUMBER) -> tuple[dict[str, str], str]:
    headers, user_id = sms_user(harness)
    consent(harness, headers, to)
    return headers, user_id


def test_send_in_simulation_walks_the_status_ladder_and_never_skips_to_delivered(
    harness: Harness,
) -> None:
    headers, _ = ready_to_send(harness)
    response = send(harness, headers)
    assert response.status_code == 202, response.text
    queued = response.json()["data"]
    assert queued["status"] == "queued"
    assert queued["is_simulated"] is True
    assert queued["segment_count"] == 1
    # The handler does not call the provider.
    assert harness.sms.sent == []

    harness.run_worker()
    assert len(harness.sms.sent) == 1
    assert message(harness, headers, queued["id"])["status"] == "accepted"

    harness.clock.advance(3)
    harness.run_worker()
    assert message(harness, headers, queued["id"])["status"] == "sent"

    harness.clock.advance(3)
    harness.run_worker()
    final = message(harness, headers, queued["id"])
    assert final["status"] == "delivered"
    assert final["is_simulated"] is True
    assert final["delivery"]["provider"] == "mock"

    rows = harness.sql(
        "select provider_message_id, is_simulated, recipient_phone from public.message_deliveries"
        " where message_id = $1",
        uuid.UUID(queued["id"]),
    )
    assert rows[0]["provider_message_id"].startswith("SIM-")
    assert rows[0]["is_simulated"] is True
    assert rows[0]["recipient_phone"] == NUMBER


def test_simulated_reply_appears_in_the_same_conversation(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    sent = send(harness, headers).json()["data"]
    harness.run_worker()
    route = harness.sql(
        "select platform_number from public.sms_routes where user_id = $1 and status = 'active'",
        uuid.UUID(user_id),
    )
    assert len(route) == 1
    platform = route[0]["platform_number"]

    callback = harness.sms.build_inbound_callback(
        from_phone=NUMBER, to_number=platform, body="Okay sige anak."
    )
    reply = harness.client.post(
        "/api/v1/webhooks/mock/inbound", content=callback.raw_body, headers=callback.headers
    )
    assert reply.status_code == 200, reply.text

    page = harness.client.get(
        f"/api/v1/sms/conversations/{sent['conversation_id']}/messages", headers=headers
    ).json()["data"]
    bodies = [(m["direction"], m["body"], m["status"]) for m in page["messages"]]
    assert bodies == [
        ("outbound", "Kumusta ka, Nanay?", "accepted"),
        ("inbound", "Okay sige anak.", "received"),
    ]
    assert page["messages"][1]["is_simulated"] is True
    conversations = harness.client.get("/api/v1/sms/conversations", headers=headers).json()["data"]
    assert conversations[0]["unread_count"] == 1
    assert NUMBER not in str(conversations)


# -- helpers for the scenarios below ----------------------------------------------------------

OTHER_COUNTRY = "+61412345678"  # Australia, fictional


@pytest.fixture(autouse=True)
def restore_reference_data(harness: Harness) -> Any:
    yield
    harness.sql(
        "update public.system_settings set value = 'false'::jsonb where key = 'sms_outbound_paused'"
    )
    harness.sql(
        "update public.sms_country_capabilities set outbound_support = 'requires_verification',"
        " inbound_support = 'requires_verification' where country_code = 'AU' and version = 1"
    )
    harness.sql(
        "delete from public.sms_country_capabilities where version > 1 and country_code in ('AU', 'US', 'PH')"
    )
    harness.sql(
        "update public.sms_country_capabilities set is_current = true where version = 1"
        " and country_code in ('AU', 'US', 'PH')"
    )


def post_callback(harness: Harness, kind: str, callback: Any) -> httpx.Response:
    return harness.client.post(
        f"/api/v1/webhooks/mock/{kind}", content=callback.raw_body, headers=callback.headers
    )


def platform_for(harness: Harness, user_id: str, remote: str = NUMBER) -> str:
    rows = harness.sql(
        "select platform_number from public.sms_routes where user_id = $1"
        " and remote_number = $2 and status = 'active'",
        uuid.UUID(user_id),
        remote,
    )
    assert len(rows) == 1
    return str(rows[0]["platform_number"])


def reply(harness: Harness, user_id: str, body: str, remote: str = NUMBER) -> httpx.Response:
    callback = harness.sms.build_inbound_callback(
        from_phone=remote, to_number=platform_for(harness, user_id, remote), body=body
    )
    return post_callback(harness, "inbound", callback)


def pump(harness: Harness, steps: int = 1, seconds: float = 0) -> None:
    for _ in range(steps):
        harness.clock.advance(seconds)
        harness.run_worker()


def deliveries(harness: Harness, message_id: str) -> list[Any]:
    return harness.sql(
        "select * from public.message_deliveries where message_id = $1 order by attempt_number",
        uuid.UUID(message_id),
    )


def admin_user(harness: Harness) -> tuple[dict[str, str], str]:
    headers, user_id = sms_user(harness)
    harness.sql("update public.profiles set role = 'admin' where id = $1", uuid.UUID(user_id))
    return headers, user_id


# -- authorisation ----------------------------------------------------------------------------


def test_unauthenticated_requests_are_rejected(harness: Harness) -> None:
    assert harness.client.get("/api/v1/sms/status").status_code == 401
    body = {"to": NUMBER, "body": "hi", "confirmed": True}
    unauthenticated = harness.client.post(
        "/api/v1/sms/messages", json=body, headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert unauthenticated.status_code == 401
    assert harness.sms.sent == []


def test_sender_without_a_verified_number_cannot_send(harness: Harness) -> None:
    _, headers = harness.onboarded_user()
    consent(harness, headers, NUMBER)
    response = send(harness, headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "sender_not_verified"
    assert harness.run_worker() == 0
    assert harness.sms.sent == []


def test_other_users_cannot_read_or_retry_my_messages(harness: Harness) -> None:
    mine, _ = ready_to_send(harness)
    theirs, _ = sms_user(harness)
    sent = send(harness, mine).json()["data"]
    assert (
        harness.client.get(f"/api/v1/sms/messages/{sent['id']}", headers=theirs).status_code == 404
    )
    assert (
        harness.client.get(
            f"/api/v1/sms/conversations/{sent['conversation_id']}/messages", headers=theirs
        ).status_code
        == 404
    )
    retry = harness.client.post(
        f"/api/v1/sms/messages/{sent['id']}/retry",
        json={"confirmed": True},
        headers={**theirs, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert retry.status_code == 404
    assert harness.client.get("/api/v1/sms/conversations", headers=theirs).json()["data"] == []


def test_sending_requires_explicit_confirmation_and_a_key(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    unconfirmed = harness.client.post(
        "/api/v1/sms/messages",
        json={"to": NUMBER, "body": "hi", "confirmed": False},
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert unconfirmed.status_code == 422
    missing_key = harness.client.post(
        "/api/v1/sms/messages",
        json={"to": NUMBER, "body": "hi", "confirmed": True},
        headers=headers,
    )
    assert missing_key.status_code == 422
    assert harness.sql("select 1 from public.messages where channel = 'sms' and body = 'hi'") == []


# -- idempotency -----------------------------------------------------------------------------


def test_duplicate_idempotency_key_sends_once(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    key = str(uuid.uuid4())
    first = send(harness, headers, key=key)
    second = send(harness, headers, key=key)
    assert (first.status_code, second.status_code) == (202, 200)
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    harness.run_worker()
    harness.run_worker()
    assert len(harness.sms.sent) == 1
    assert len(deliveries(harness, first.json()["data"]["id"])) == 1

    conflict = send(harness, headers, key=key, body="A different message")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


# -- consent, opt-out, country, size --------------------------------------------------------------


def test_consent_is_required_per_recipient_and_can_be_withdrawn(harness: Harness) -> None:
    headers, user_id = sms_user(harness)
    blocked = send(harness, headers)
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "consent_required"
    assert (
        harness.sql("select 1 from public.messages where sender_user_id = $1", uuid.UUID(user_id))
        == []
    )

    consent(harness, headers, NUMBER)
    assert send(harness, headers).status_code == 202
    # Consent for one number is not consent for another.
    assert send(harness, headers, to=OTHER_COUNTRY).json()["error"]["code"] == "consent_required"

    consent(harness, headers, NUMBER, "withdrawn")
    assert send(harness, headers).json()["error"]["code"] == "consent_required"
    history = harness.sql(
        "select decision from public.user_consents where consent_type = 'sms_sender_attestation'"
        " order by created_at"
    )
    assert "withdrawn" in [r["decision"] for r in history]


def test_opt_out_keyword_blocks_everyone_until_the_recipient_opts_back_in(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    other, _ = ready_to_send(harness)
    sent = send(harness, headers).json()["data"]
    harness.run_worker()

    assert reply(harness, user_id, "STOP").status_code == 200
    page = harness.client.get(
        f"/api/v1/sms/conversations/{sent['conversation_id']}/messages", headers=headers
    ).json()["data"]
    assert [m["direction"] for m in page["messages"]] == ["outbound"]  # the keyword is not chat

    for who in (headers, other):
        blocked = send(harness, who)
        assert blocked.status_code == 422
        assert blocked.json()["error"]["code"] == "recipient_opted_out"
    notices = harness.sql(
        "select title from public.notifications where user_id = $1 and notification_type = 'system'",
        uuid.UUID(user_id),
    )
    assert len(notices) == 1
    audit = harness.sql(
        "select target_id from public.audit_logs where action = 'sms.opt_out_recorded'"
    )
    assert audit and all(NUMBER not in r["target_id"] for r in audit)

    assert reply(harness, user_id, "start").status_code == 200
    assert send(harness, headers).status_code == 202


def test_keyword_inside_a_sentence_is_a_normal_reply(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    send(harness, headers)
    harness.run_worker()
    assert reply(harness, user_id, "please stop by later").status_code == 200
    assert harness.sql("select 1 from public.sms_opt_outs") == []
    assert (
        harness.client.get("/api/v1/sms/conversations", headers=headers).json()["data"][0][
            "unread_count"
        ]
        == 1
    )


def test_unknown_country_and_unsupported_routes_are_refused(harness: Harness) -> None:
    headers, _ = sms_user(harness)
    china = "+8613800138000"
    consent(harness, headers, china)
    refused = send(harness, headers, to=china)
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "country_unsupported"

    harness.sql(
        "update public.sms_country_capabilities set outbound_support = 'unsupported'"
        " where country_code = 'AU' and version = 1"
    )
    consent(harness, headers, OTHER_COUNTRY)
    assert send(harness, headers, to=OTHER_COUNTRY).json()["error"]["code"] == "country_unsupported"
    assert harness.sms.sent == []


def test_invalid_and_special_numbers_are_refused(harness: Harness) -> None:
    headers, _ = sms_user(harness)
    for bad in ("12345", "+63123", "+18005550199", "not a number"):
        response = send(harness, headers, to=bad)
        assert response.status_code == 422, bad


def test_local_format_needs_a_country_and_normalises(harness: Harness) -> None:
    headers, _ = sms_user(harness)
    local = "0917 123 4567"
    assert send(harness, headers, to=local).status_code == 422
    quote = harness.client.post(
        "/api/v1/sms/quote", json={"to": local, "country_code": "PH", "body": "Hi"}, headers=headers
    )
    assert quote.status_code == 200, quote.text
    assert quote.json()["data"]["recipient"]["masked_phone"] == "+63****4567"
    assert quote.json()["data"]["recipient"]["country_code"] == "PH"


def test_quote_reports_segments_cost_consent_and_warnings(harness: Harness) -> None:
    headers, _ = sms_user(harness)

    def quote(body: str, to: str = NUMBER) -> dict[str, Any]:
        response = harness.client.post(
            "/api/v1/sms/quote", json={"to": to, "body": body}, headers=headers
        )
        assert response.status_code == 200, response.text
        data: dict[str, Any] = response.json()["data"]
        return data

    one = quote("Hello")
    assert one["segment"]["segments"] == 1
    assert one["segment"]["encoding"] == "gsm7"
    assert one["cost"] == {
        "units": 100,
        "credits": 1.0,
        "source": "demo_default",
        "estimated": True,
    }
    assert one["mode"] == "simulation"
    assert one["is_simulated"] is True
    assert one["availability"] == "simulation_only"
    assert one["consent"]["required"] is True and one["consent"]["granted"] is False
    assert {b["code"] for b in one["blockers"]} == {"consent_required"}
    assert one["can_send"] is False
    assert any("not verified" in w for w in one["warnings"])
    assert NUMBER not in str(one)

    assert quote("日本語")["segment"]["encoding"] == "ucs2"
    assert quote("a" * 161)["segment"]["segments"] == 2
    assert quote("a" * 161)["cost"]["units"] == 200
    too_long = quote("a" * 1600)
    assert too_long["segment"]["too_long"] is True
    assert "message_too_long" in {b["code"] for b in too_long["blockers"]}

    consent(harness, headers, NUMBER)
    ready = quote("Hello")
    assert ready["consent"]["granted"] is True
    assert ready["can_send"] is True


def test_overlong_message_is_refused_and_not_stored(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    response = send(harness, headers, body="a" * 1600)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "message_too_long"
    assert harness.sql("select 1 from public.messages where char_count = 1600") == []


def test_capabilities_never_promise_universal_two_way_sms(harness: Harness) -> None:
    headers, _ = sms_user(harness)
    countries = {
        c["country_code"]: c
        for c in harness.client.get("/api/v1/sms/countries", headers=headers).json()["data"]
    }
    ph = countries["PH"]
    assert ph["registered_sender_required"] is True
    assert ph["registered_sender_status"] == "not_registered"
    assert ph["replies"] == "unverified"
    assert ph["availability"] == "simulation_only"
    assert "promotional" in (ph["content_restrictions"] or "")
    assert all(c["replies"] != "supported" for c in countries.values())

    one = harness.client.get("/api/v1/sms/capability?country_code=ph", headers=headers)
    assert one.json()["data"]["country_code"] == "PH"
    by_number = harness.client.get(
        "/api/v1/sms/capability?phone_number=%2B639171234567", headers=headers
    )
    assert by_number.json()["data"]["country_code"] == "PH"
    assert (
        harness.client.get("/api/v1/sms/capability?country_code=ZZ", headers=headers).status_code
        == 404
    )
    assert harness.client.get("/api/v1/sms/capability", headers=headers).status_code == 422


def test_status_endpoint_labels_the_mode(harness: Harness) -> None:
    headers, _ = sms_user(harness)
    data = harness.client.get("/api/v1/sms/status", headers=headers).json()["data"]
    assert (data["mode"], data["provider"], data["is_simulated"]) == ("simulation", "mock", True)
    assert data["sender_verified"] is True
    assert "no real SMS" in data["notice"]


# -- delivery scenarios ------------------------------------------------------------------------


def test_failed_delivery_shows_a_readable_reason_notifies_and_can_be_retried(
    harness: Harness,
) -> None:
    number = "+12025550101"
    headers, user_id = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    pump(harness)
    pump(harness, seconds=3)
    failed = message(harness, headers, sent["id"])
    assert failed["status"] == "failed"
    assert failed["failure"]["is_permanent"] is True
    assert failed["failure"]["may_have_been_delivered"] is False
    assert failed["failure"]["reason"].startswith("Simulated failure")
    assert failed["failure"]["code"] == "SIM-FAILED"
    assert failed["can_retry"] is True
    assert len(deliveries(harness, sent["id"])) == 1  # a callback failure is never auto-resent
    notices = harness.sql(
        "select title from public.notifications where user_id = $1 and notification_type = 'sms_failed'",
        uuid.UUID(user_id),
    )
    assert [n["title"] for n in notices] == ["Simulated SMS could not be sent"]

    resend = harness.client.post(
        f"/api/v1/sms/messages/{sent['id']}/retry",
        json={"confirmed": True},
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resend.status_code == 202, resend.text
    assert resend.json()["data"]["id"] != sent["id"]
    assert resend.json()["data"]["body"] == sent["body"]
    # Only failed messages can be sent again.
    delivered = send(harness, ready_to_send(harness)[0]).json()["data"]
    again = harness.client.post(
        f"/api/v1/sms/messages/{delivered['id']}/retry",
        json={"confirmed": True},
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert again.status_code == 404


def test_undelivered_is_not_delivered(harness: Harness) -> None:
    number = "+12025550102"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    pump(harness)
    pump(harness, seconds=3)
    pump(harness, seconds=3)
    final = message(harness, headers, sent["id"])
    assert final["status"] == "undelivered"
    assert final["delivery"]["delivered_at"] is None
    assert final["failure"]["reason"].startswith("Simulated failure")


def test_transient_failure_is_retried_with_the_same_key_and_then_accepted(harness: Harness) -> None:
    number = "+12025550103"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    harness.run_worker()
    assert message(harness, headers, sent["id"])["status"] == "retrying"
    assert harness.sms.sent == []

    pump(harness, seconds=30)
    assert len(harness.sms.sent) == 1
    assert message(harness, headers, sent["id"])["status"] == "accepted"
    rows = deliveries(harness, sent["id"])
    assert [(r["attempt_number"], r["status"]) for r in rows] == [(1, "failed"), (2, "accepted")]
    assert rows[0]["failure_class"] == "transient" and rows[0]["is_permanent"] is False
    assert rows[1]["retry_of_delivery_id"] == rows[0]["id"]
    # One idempotency key for every attempt.
    assert len({r.idempotency_key for r in harness.sms.sent}) == 1


def test_transient_failures_stop_at_the_attempt_limit(harness: Harness) -> None:
    number = "+12025550104"
    headers, user_id = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    for _ in range(6):
        pump(harness, seconds=400)
    rows = deliveries(harness, sent["id"])
    assert len(rows) == 3  # provider_configurations.max_retry_attempts
    assert [r["status"] for r in rows] == ["failed", "failed", "failed"]
    assert [r["is_permanent"] for r in rows] == [False, False, True]
    assert rows[-1]["failure_code"] == "retries_exhausted"
    final = message(harness, headers, sent["id"])
    assert final["status"] == "failed"
    assert final["failure"]["is_permanent"] is True
    assert harness.sms.sent == []
    assert (
        len(
            harness.sql(
                "select 1 from public.notifications where user_id = $1 and notification_type = 'sms_failed'",
                uuid.UUID(user_id),
            )
        )
        == 1
    )
    # Nothing further is ever scheduled.
    pump(harness, seconds=3600)
    assert len(deliveries(harness, sent["id"])) == 3


def test_permanent_provider_errors_are_not_retried(harness: Harness) -> None:
    number = "+12025550105"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    for _ in range(3):
        pump(harness, seconds=400)
    rows = deliveries(harness, sent["id"])
    assert len(rows) == 1
    assert (rows[0]["status"], rows[0]["failure_class"], rows[0]["is_permanent"]) == (
        "failed",
        "permanent",
        True,
    )
    assert (
        message(harness, headers, sent["id"])["failure"]["reason"]
        == "The phone number is not valid."
    )


def test_ambiguous_outcome_is_not_resent_and_resolves_to_failed_with_a_warning(
    harness: Harness,
) -> None:
    number = "+12025550110"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    harness.run_worker()
    held = message(harness, headers, sent["id"])
    assert held["status"] == "queued"  # held, not failed, not resent
    pump(harness, seconds=300)
    assert len(deliveries(harness, sent["id"])) == 1
    assert message(harness, headers, sent["id"])["status"] == "queued"

    pump(harness, seconds=700)  # past the 15 minute resolution window
    final = message(harness, headers, sent["id"])
    assert final["status"] == "failed"
    assert final["failure"]["may_have_been_delivered"] is True
    assert final["failure"]["code"] == "outcome_unknown"
    assert len(deliveries(harness, sent["id"])) == 1
    assert harness.sms.sent == []


def test_late_callback_corrects_an_ambiguous_failure_forward(harness: Harness) -> None:
    number = "+12025550110"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    harness.run_worker()
    pump(harness, seconds=1000)
    assert message(harness, headers, sent["id"])["status"] == "failed"
    delivery_id = deliveries(harness, sent["id"])[0]["id"]

    from app.integrations.sms.base import SendRequest

    # Evidence arrives: the provider did accept it. Build the callback the provider would send.
    harness.sms._records["SIM-LATE"] = type(
        "R",
        (),
        {
            "request": SendRequest(
                to=number,
                body="x",
                sender="+12025550190",
                correlation_id=delivery_id,
                idempotency_key="k",
            ),
            "events": [],
        },
    )()
    from app.integrations.sms.mock import _Scheduled

    event = _Scheduled(
        due_at=harness.clock.now,
        message_id="SIM-LATE",
        status="delivered",
        error_code=None,
        correlation_id=delivery_id,
        event_id="SIM-LATE:delivered",
    )
    callback = harness.sms._status_callback(event)
    assert post_callback(harness, "status", callback).status_code == 200
    corrected = message(harness, headers, sent["id"])
    assert corrected["status"] == "delivered"
    assert corrected["failure"] is None
    audit = harness.sql("select 1 from public.audit_logs where action = 'sms.status_corrected'")
    assert audit


def test_no_receipt_route_stays_sent_and_is_labelled_unconfirmed(harness: Harness) -> None:
    number = "+12025550107"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    pump(harness)
    pump(harness, seconds=3)
    for _ in range(4):
        pump(harness, seconds=3600 * 8)
    final = message(harness, headers, sent["id"])
    assert final["status"] == "sent"
    assert final["delivery"]["confirmation"] == "unconfirmed"
    assert final["delivery"]["delivered_at"] is None


def test_out_of_order_callbacks_never_regress_status(harness: Harness) -> None:
    number = "+12025550109"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    pump(harness)
    pump(harness, seconds=3)
    assert message(harness, headers, sent["id"])["status"] == "delivered"
    pump(harness, seconds=3)  # the late "sent" arrives
    assert message(harness, headers, sent["id"])["status"] == "delivered"
    detail = harness.client.get(f"/api/v1/sms/messages/{sent['id']}", headers=headers).json()[
        "data"
    ]
    ignored = [e for e in detail["events"] if not e["applied"]]
    assert [e["status"] for e in ignored] == ["sent"]


def test_duplicate_status_callbacks_are_recorded_once(harness: Harness) -> None:
    number = "+12025550108"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    pump(harness)
    pump(harness, seconds=3)
    pump(harness, seconds=3)
    pump(harness, seconds=3)
    assert message(harness, headers, sent["id"])["status"] == "delivered"
    events = harness.sql(
        "select normalised_status from public.message_delivery_events e join"
        " public.message_deliveries d on d.id = e.delivery_id where d.message_id = $1",
        uuid.UUID(sent["id"]),
    )
    assert [e["normalised_status"] for e in events].count("delivered") == 1
    notices = harness.sql(
        "select 1 from public.notifications where notification_type = 'sms_delivered'"
        " and reference_id = $1",
        uuid.UUID(sent["id"]),
    )
    assert len(notices) == 1


def test_delayed_delivery_waits_for_the_callback(harness: Harness) -> None:
    number = "+12025550106"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    pump(harness)
    pump(harness, seconds=60)
    assert message(harness, headers, sent["id"])["status"] == "sent"
    pump(harness, seconds=600)
    assert message(harness, headers, sent["id"])["status"] == "delivered"


def test_lost_callbacks_are_recovered_by_polling(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    sent = send(harness, headers).json()["data"]
    harness.run_worker()
    harness.clock.advance(10)

    async def swallow() -> None:
        await harness.sms.pending_callbacks()

    harness.client.portal.call(swallow)  # type: ignore[union-attr]
    assert message(harness, headers, sent["id"])["status"] == "accepted"
    pump(harness, seconds=400)
    assert message(harness, headers, sent["id"])["status"] == "delivered"
    sources = harness.sql(
        "select source from public.message_delivery_events e join public.message_deliveries d"
        " on d.id = e.delivery_id where d.message_id = $1 and e.applied",
        uuid.UUID(sent["id"]),
    )
    assert "poll" in [s["source"] for s in sources]


def test_provider_response_is_stored_without_the_message_body(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    body = "A private sentence that must not be stored beside the provider response"
    sent = send(harness, headers, body=body).json()["data"]
    harness.run_worker()
    row = deliveries(harness, sent["id"])[0]
    assert row["provider_message_id"].startswith("SIM-")
    assert row["provider_status"] == "accepted"
    assert body not in str(row["provider_response"])
    assert NUMBER not in str(row["provider_response"])


# -- webhooks -------------------------------------------------------------------------------


def test_invalid_signatures_are_rejected_without_side_effects(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    send(harness, headers)
    harness.run_worker()
    platform = platform_for(harness, user_id)
    before = harness.sql("select count(*) as n from public.provider_webhooks")[0]["n"]

    callback = harness.sms.build_inbound_callback(
        from_phone=NUMBER, to_number=platform, body="legit"
    )
    tampered = harness.client.post(
        "/api/v1/webhooks/mock/inbound",
        content=callback.raw_body.replace(b"legit", b"evil!"),
        headers=callback.headers,
    )
    unsigned = harness.client.post("/api/v1/webhooks/mock/inbound", content=callback.raw_body)
    wrong_key = harness.client.post(
        "/api/v1/webhooks/mock/inbound",
        content=callback.raw_body,
        headers={**callback.headers, "x-mock-signature": "0" * 64},
    )
    harness.clock.advance(3600)
    stale = post_callback(harness, "inbound", callback)
    for response in (tampered, unsigned, wrong_key, stale):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "invalid_signature"
    assert harness.sql("select count(*) as n from public.provider_webhooks")[0]["n"] == before
    rejected = harness.sql(
        "select ip_prefix, metadata::text as m from public.audit_logs"
        " where action = 'sms.webhook_rejected'"
    )
    assert len(rejected) >= 4
    assert all("evil" not in r["m"] and "legit" not in r["m"] for r in rejected)


def test_webhook_for_a_provider_that_is_not_running_does_not_exist(harness: Harness) -> None:
    for kind in ("inbound", "status"):
        assert (
            harness.client.post(f"/api/v1/webhooks/twilio/{kind}", content=b"x=1").status_code
            == 404
        )


def test_malformed_signed_payload_is_a_400_and_stores_nothing(harness: Harness) -> None:
    from app.integrations.sms.mock import SIGNATURE_HEADER, TIMESTAMP_HEADER, sign

    raw = b"not json"
    stamp = str(int(harness.clock.now.timestamp()))
    response = harness.client.post(
        "/api/v1/webhooks/mock/inbound",
        content=raw,
        headers={
            TIMESTAMP_HEADER: stamp,
            SIGNATURE_HEADER: sign("test-only-mock-webhook-secret", stamp, raw),
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_webhook"


def test_replayed_inbound_webhook_creates_one_message(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    sent = send(harness, headers).json()["data"]
    harness.run_worker()
    callback = harness.sms.build_inbound_callback(
        from_phone=NUMBER,
        to_number=platform_for(harness, user_id),
        body="once",
        message_id="SIM-IN-1",
    )
    for _ in range(10):
        assert post_callback(harness, "inbound", callback).status_code == 200
    page = harness.client.get(
        f"/api/v1/sms/conversations/{sent['conversation_id']}/messages", headers=headers
    ).json()["data"]
    assert [m["body"] for m in page["messages"] if m["direction"] == "inbound"] == ["once"]
    assert (
        harness.sql(
            "select count(*) as n from public.provider_webhooks where dedupe_key = 'SIM-IN-1'"
        )[0]["n"]
        == 1
    )
    assert (
        harness.sql(
            "select count(*) as n from public.notifications where notification_type = 'sms_inbound'"
            " and user_id = $1",
            uuid.UUID(user_id),
        )[0]["n"]
        == 1
    )


def test_concurrent_duplicate_webhooks_create_one_message(harness: Harness) -> None:
    from concurrent.futures import ThreadPoolExecutor

    headers, user_id = ready_to_send(harness)
    send(harness, headers)
    harness.run_worker()
    callback = harness.sms.build_inbound_callback(
        from_phone=NUMBER,
        to_number=platform_for(harness, user_id),
        body="race",
        message_id="SIM-IN-RACE",
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: post_callback(harness, "inbound", callback), range(4)))
    assert [r.status_code for r in responses] == [200] * 4
    assert harness.sql("select count(*) as n from public.messages where body = 'race'")[0]["n"] == 1


def test_reply_from_an_unknown_route_is_kept_for_admins_and_shown_to_nobody(
    harness: Harness,
) -> None:
    admin, _ = admin_user(harness)
    user, _ = ready_to_send(harness)
    send(harness, user)
    callback = harness.sms.build_inbound_callback(
        from_phone="+12025550177", to_number=PLATFORM, body="who is this"
    )
    assert post_callback(harness, "inbound", callback).status_code == 200
    stored = harness.sql(
        "select routing_result, processing_status, raw_payload->>'body' as body"
        " from public.provider_webhooks where dedupe_key = $1",
        json_id(callback),
    )
    assert (stored[0]["routing_result"], stored[0]["processing_status"]) == (
        "unrouted",
        "processed",
    )
    assert harness.sql("select 1 from public.messages where body = 'who is this'") == []
    assert harness.sms.sent == [] and not harness.sql(
        "select 1 from public.message_deliveries where recipient_phone = '+12025550177'"
    )

    queue = harness.client.get("/api/v1/admin/sms/inbound/unrouted", headers=admin)
    assert queue.status_code == 200
    first = queue.json()["data"][0]
    assert first["masked_sender"] == "+12****0177"
    assert "who is this" not in queue.text and "+12025550177" not in queue.text
    assert harness.client.get("/api/v1/admin/sms/inbound/unrouted", headers=user).status_code == 403


def json_id(callback: Any) -> str:
    import json

    return str(json.loads(callback.raw_body)["event_id"])


def test_reply_from_a_blocked_number_is_stored_hidden_and_not_notified(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    sent = send(harness, headers).json()["data"]
    harness.run_worker()
    harness.sql(
        "insert into public.user_blocks (blocker_id, blocked_phone) values ($1, $2)",
        uuid.UUID(user_id),
        NUMBER,
    )
    assert reply(harness, user_id, "hello?").status_code == 200
    page = harness.client.get(
        f"/api/v1/sms/conversations/{sent['conversation_id']}/messages", headers=headers
    ).json()["data"]
    assert [m["direction"] for m in page["messages"]] == ["outbound"]
    assert harness.sql("select 1 from public.messages where body = 'hello?'")
    assert not harness.sql(
        "select 1 from public.notifications where user_id = $1 and notification_type = 'sms_inbound'",
        uuid.UUID(user_id),
    )
    # You can no longer text a number you blocked.
    assert send(harness, headers).json()["error"]["code"] == "user_blocked"


def test_replies_reach_only_the_user_who_owns_the_route(harness: Harness) -> None:
    alice, alice_id = ready_to_send(harness)
    bob, bob_id = ready_to_send(harness)
    send(harness, alice)
    send(harness, bob)
    harness.run_worker()
    assert platform_for(harness, alice_id) != platform_for(harness, bob_id)
    assert reply(harness, bob_id, "for bob only").status_code == 200
    for who, expected in ((alice, 0), (bob, 1)):
        conversations = harness.client.get("/api/v1/sms/conversations", headers=who).json()["data"]
        assert conversations[0]["unread_count"] == expected


def test_reply_marks_read_and_unarchives(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    sent = send(harness, headers).json()["data"]
    harness.run_worker()
    conversation_id = sent["conversation_id"]
    reply(harness, user_id, "one")
    reply_two = harness.sms.build_inbound_callback(
        from_phone=NUMBER, to_number=platform_for(harness, user_id), body="two"
    )
    post_callback(harness, "inbound", reply_two)
    page = harness.client.get(
        f"/api/v1/sms/conversations/{conversation_id}/messages", headers=headers
    ).json()["data"]
    top = max(m["seq"] for m in page["messages"])
    state = harness.client.post(
        f"/api/v1/sms/conversations/{conversation_id}/read",
        json={"up_to_seq": top},
        headers=headers,
    ).json()["data"]
    assert state["unread_count"] == 0


def test_reply_after_the_route_expired_is_unrouted(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    send(harness, headers)
    harness.run_worker()
    platform = platform_for(harness, user_id)
    harness.sql(
        "update public.sms_routes set expires_at = now() - interval '1 day' where user_id = $1",
        uuid.UUID(user_id),
    )
    callback = harness.sms.build_inbound_callback(
        from_phone=NUMBER, to_number=platform, body="late"
    )
    assert post_callback(harness, "inbound", callback).status_code == 200
    assert (
        harness.sql(
            "select routing_result from public.provider_webhooks where dedupe_key = $1",
            json_id(callback),
        )[0]["routing_result"]
        == "unrouted"
    )


def test_a_sender_number_is_never_shared_by_two_users_for_one_recipient(harness: Harness) -> None:
    users = [ready_to_send(harness) for _ in range(3)]
    for headers, _ in users:
        assert send(harness, headers).status_code == 202
    fourth, _ = ready_to_send(harness)
    full = send(harness, fourth)
    assert full.status_code == 503
    assert full.json()["error"]["code"] == "sender_capacity"


# -- operations ---------------------------------------------------------------------------------


def test_outbound_pause_switch_blocks_sending(harness: Harness) -> None:
    admin, _ = admin_user(harness)
    headers, _ = ready_to_send(harness)
    paused = harness.client.put(
        "/api/v1/admin/sms/outbound-paused", json={"paused": True}, headers=admin
    )
    assert paused.status_code == 200
    response = send(harness, headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "sms_paused"


def test_mode_mismatch_fails_loudly_instead_of_switching_modes(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    harness.sql("update public.provider_configurations set is_active = false")
    harness.sql(
        "update public.provider_configurations set is_active = true, live_confirmed_at = now(),"
        " live_confirmed_by = (select id from public.profiles limit 1),"
        " live_confirmed_environment = 'test' where provider = 'twilio'"
    )
    response = send(harness, headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "sms_mode_mismatch"
    assert harness.sms.sent == []


def test_queued_message_is_held_while_a_different_provider_is_active(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    sent = send(harness, headers).json()["data"]
    harness.sql("update public.provider_configurations set is_active = false")
    harness.sql(
        "update public.provider_configurations set is_active = true, live_confirmed_at = now(),"
        " live_confirmed_by = (select id from public.profiles limit 1),"
        " live_confirmed_environment = 'test' where provider = 'twilio'"
    )
    harness.run_worker()
    assert harness.sms.sent == []  # never sent through a different mode
    assert message(harness, headers, sent["id"])["status"] == "queued"

    harness.sql("update public.provider_configurations set is_active = false")
    harness.sql(
        "update public.provider_configurations set is_active = true where provider = 'mock'"
    )
    pump(harness, seconds=61)
    assert len(harness.sms.sent) == 1
    assert message(harness, headers, sent["id"])["status"] == "accepted"


def test_audit_trail_has_no_numbers_or_message_text(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    body = "Secret text for the audit test"
    send(harness, headers, body=body)
    pump(harness)
    pump(harness, seconds=10)
    rows = harness.sql(
        "select action, target_id, metadata::text as m from public.audit_logs where category = 'sms'"
    )
    actions = {r["action"] for r in rows}
    assert {"sms.queued", "sms.dispatched", "sms.delivered"} <= actions
    for row in rows:
        assert NUMBER not in row["m"] + (row["target_id"] or "")
        assert body not in row["m"]


def test_simulation_spends_demo_credits_and_never_touches_live_credits(harness: Harness) -> None:
    """Simulated sends use the separate demo ledger. Real credit is never charged for them."""
    headers, user_id = ready_to_send(harness)
    sent = send(harness, headers).json()["data"]
    pump(harness)
    message_id = uuid.UUID(sent["id"])
    row = harness.sql(
        "select credit_cost_units, is_simulated from public.messages where id = $1", message_id
    )[0]
    assert row["is_simulated"] is True and row["credit_cost_units"] > 0
    entries = harness.sql(
        "select ledger_type, entry_type from public.credit_transactions where message_id = $1",
        message_id,
    )
    assert {(e["ledger_type"], e["entry_type"]) for e in entries} == {
        ("demo", "reservation"),
        ("demo", "deduction"),
    }
    live = harness.sql(
        "select balance_units, reserved_units from public.messaging_credits "
        "where user_id = $1 and ledger_type = 'live'",
        uuid.UUID(user_id),
    )[0]
    assert (live["balance_units"], live["reserved_units"]) == (0, 0)


# -- administration -----------------------------------------------------------------------------


def test_admin_endpoints_require_the_admin_role(harness: Harness) -> None:
    user, _ = sms_user(harness)
    for method, path in (
        ("get", "/api/v1/admin/sms/providers"),
        ("get", "/api/v1/admin/sms/capabilities"),
        ("get", "/api/v1/admin/sms/monitoring"),
        ("get", "/api/v1/admin/sms/inbound/unrouted"),
    ):
        assert getattr(harness.client, method)(path, headers=user).status_code == 403, path
        assert getattr(harness.client, method)(path).status_code == 401, path
    simulate = harness.client.post(
        "/api/v1/admin/sms/simulate/inbound",
        json={"from_phone": NUMBER, "to_number": PLATFORM, "body": "x"},
        headers=user,
    )
    assert simulate.status_code == 403


def test_admin_provider_view_never_exposes_secrets(harness: Harness) -> None:
    admin, _ = admin_user(harness)
    response = harness.client.get("/api/v1/admin/sms/providers", headers=admin)
    assert response.status_code == 200
    text = response.text
    assert "secret_ref" not in text and "TWILIO_AUTH_TOKEN" not in text
    assert "test-only-mock-webhook-secret" not in text
    providers = {p["provider"]: p for p in response.json()["data"]}
    assert providers["mock"]["is_running"] is True and providers["twilio"]["is_running"] is False
    assert providers["twilio"]["credentials_configured"] is False
    assert all("+1202555" not in n for n in providers["mock"]["sender_numbers"])

    rejected = harness.client.patch(
        f"/api/v1/admin/sms/providers/{providers['twilio']['id']}",
        json={"auth_token": "super-secret"},
        headers=admin,
    )
    assert rejected.status_code == 422
    assert "super-secret" not in rejected.text


def test_admin_updates_retry_settings_and_cannot_activate_a_provider_that_is_not_running(
    harness: Harness,
) -> None:
    admin, _ = admin_user(harness)
    providers = {
        p["provider"]: p
        for p in harness.client.get("/api/v1/admin/sms/providers", headers=admin).json()["data"]
    }
    mock_id, twilio_id = providers["mock"]["id"], providers["twilio"]["id"]
    updated = harness.client.patch(
        f"/api/v1/admin/sms/providers/{mock_id}", json={"max_retry_attempts": 4}, headers=admin
    )
    assert updated.status_code == 200
    harness.sql(
        "update public.provider_configurations set max_retry_attempts = 3 where provider = 'mock'"
    )
    bad = harness.client.patch(
        f"/api/v1/admin/sms/providers/{mock_id}",
        json={"retry_base_seconds": 100, "retry_cap_seconds": 10},
        headers=admin,
    )
    assert bad.status_code == 422
    blocked = harness.client.post(
        f"/api/v1/admin/sms/providers/{twilio_id}/activate",
        json={"confirm_environment": "test"},
        headers=admin,
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "provider_not_running"


def test_admin_capability_changes_are_versioned_and_guarded(harness: Harness) -> None:
    admin, _ = admin_user(harness)
    base: dict[str, Any] = {
        "country_name": "Australia",
        "outbound_support": "supported",
        "inbound_support": "requires_verification",
        "alphanumeric_sender_allowed": False,
        "registered_sender_required": False,
        "registered_sender_status": "not_required",
        "supported_number_types": ["mobile"],
        "price_units_per_segment": 8,
        "verified": True,
    }
    put = harness.client.put("/api/v1/admin/sms/capabilities/AU", json=base, headers=admin)
    assert put.status_code == 200, put.text
    assert put.json()["data"]["version"] == 2 and put.json()["data"]["verified"] is True
    versions = harness.sql(
        "select version, is_current from public.sms_country_capabilities where country_code = 'AU'"
        " order by version"
    )
    assert [(v["version"], v["is_current"]) for v in versions] == [(1, False), (2, True)]

    unverified = harness.client.put(
        "/api/v1/admin/sms/capabilities/AU", json={**base, "verified": False}, headers=admin
    )
    assert unverified.status_code == 422
    assert unverified.json()["error"]["code"] == "capability_rejected"
    ph = harness.client.put(
        "/api/v1/admin/sms/capabilities/PH",
        json={**base, "country_name": "Philippines", "outbound_support": "requires_verification"},
        headers=admin,
    )
    assert ph.status_code == 422  # a Philippine route needs an explicit registration status
    registration = harness.client.put(
        "/api/v1/admin/sms/capabilities/PH",
        json={
            **base,
            "country_name": "Philippines",
            "outbound_support": "supported",
            "registered_sender_required": True,
            "registered_sender_status": "pending",
        },
        headers=admin,
    )
    assert registration.status_code == 422  # supported needs the sender registered
    # Failed publishes leave the current rules untouched.
    current = harness.sql(
        "select count(*) as n from public.sms_country_capabilities where country_code = 'PH' and is_current"
    )
    assert current[0]["n"] == 1


def test_admin_monitoring_summarises_health_without_content(harness: Harness) -> None:
    admin, _ = admin_user(harness)
    good, _ = ready_to_send(harness)
    send(harness, good)
    pump(harness)
    pump(harness, seconds=10)
    number = "+12025550101"
    bad, _ = ready_to_send(harness, number)
    send(harness, bad, to=number, body="secret failing text")
    pump(harness)
    pump(harness, seconds=10)
    data = harness.client.get("/api/v1/admin/sms/monitoring", headers=admin).json()["data"]
    assert data["mode"] == "simulation" and data["provider"] == "mock"
    assert data["delivery_rate"] is not None and 0 < data["delivery_rate"] < 1
    assert data["failure_rate"] is not None
    assert data["recent_failures"][0]["masked_recipient"] == "+12****0101"
    assert "secret failing text" not in str(data) and number not in str(data)


def test_admin_can_simulate_a_reply_through_the_signed_path_and_replay_it(harness: Harness) -> None:
    admin, admin_id = ready_to_send_admin(harness)
    send(harness, admin)
    harness.run_worker()
    payload = {
        "from_phone": NUMBER,
        "to_number": platform_for(harness, admin_id),
        "body": "Simulated hello",
        "replay_id": "SIM-IN-ADMIN-1",
    }
    first = harness.client.post("/api/v1/admin/sms/simulate/inbound", json=payload, headers=admin)
    assert first.status_code == 200, first.text
    assert first.json()["data"] == {"duplicate": False, "routing_result": "routed"}
    again = harness.client.post("/api/v1/admin/sms/simulate/inbound", json=payload, headers=admin)
    assert again.json()["data"]["duplicate"] is True
    stored = harness.sql("select is_simulated from public.messages where body = 'Simulated hello'")
    assert len(stored) == 1 and stored[0]["is_simulated"] is True


def ready_to_send_admin(harness: Harness) -> tuple[dict[str, str], str]:
    headers, user_id = admin_user(harness)
    consent(harness, headers, NUMBER)
    return headers, user_id


def test_reply_simulation_is_refused_in_production(harness: Harness) -> None:
    admin, _ = admin_user(harness)
    object.__setattr__(harness.settings, "app_env", "production")
    try:
        response = harness.client.post(
            "/api/v1/admin/sms/simulate/inbound",
            json={"from_phone": NUMBER, "to_number": PLATFORM, "body": "x"},
            headers=admin,
        )
    finally:
        object.__setattr__(harness.settings, "app_env", "test")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "simulation_unavailable"
