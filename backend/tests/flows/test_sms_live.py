"""Live mode (Twilio) end to end, with Twilio replaced by an in-process fake.

No request leaves the machine: TwilioSmsProvider talks to an httpx MockTransport that records what
would have been sent. Webhooks are signed with Twilio's real algorithm using a fake token, so
this exercises the same signature code a real callback would hit.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
import pytest

from app.integrations.sms.twilio import TwilioSmsProvider, compute_signature, parse_form
from tests.flows.conftest import Harness, build_harness
from tests.flows.test_sms import admin_user, message, sms_user

TOKEN = "fake-twilio-token"
SID = "ACfaketestaccount"
BASE = "https://api.example.test"
SG_NUMBER = "+6591234567"  # fictional
POOL_NUMBER = "+12025550193"


@dataclass
class LiveEnv:
    calls: list[dict[str, str]] = field(default_factory=list)
    reply: tuple[int, dict[str, Any], dict[str, str]] = (201, {}, {})
    harness: Harness | None = None
    sids: list[str] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        status, payload, headers = self.reply
        if request.method == "POST":
            form = {k: v[0] for k, v in parse_form(request.content).items()}
            self.calls.append(form)
            self.sids.append(f"SM{uuid.uuid4().hex}")
            if status == 201 and not payload:
                payload = {
                    "sid": self.sids[-1],
                    "status": "queued",
                    "num_segments": "1",
                }
        return httpx.Response(status, json=payload, headers=headers)


@pytest.fixture
def live(database_url: str) -> Any:
    env = LiveEnv()

    def factory(_: Any) -> TwilioSmsProvider:
        return TwilioSmsProvider(
            account_sid=SID,
            auth_token=TOKEN,
            client=httpx.AsyncClient(transport=httpx.MockTransport(env.handle)),
        )

    for harness in build_harness(
        database_url,
        provider_factory=factory,
        settings_extra={
            "sms_provider_mode": "live",
            "sms_live_confirmed": True,
            "twilio_account_sid": SID,
            "twilio_auth_token": TOKEN,
            "sms_public_base_url": BASE,
        },
    ):
        env.harness = harness
        yield env


def live_user(harness: Harness) -> tuple[dict[str, str], str]:
    """A user with a number verified for live mode (simulated verification is not enough)."""
    headers, user_id = sms_user(harness)
    harness.sql(
        "insert into public.phone_numbers (user_id, e164, country_code, verification_mode,"
        " status, verified_at) values ($1, $2, 'PH', 'live', 'verified', now())",
        uuid.UUID(user_id),
        f"+63918{uuid.uuid4().int % 10_000_000:07d}",
    )
    return headers, user_id


def capability_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "country_name": "Singapore",
        "outbound_support": "supported",
        "inbound_support": "requires_verification",
        "alphanumeric_sender_allowed": False,
        "registered_sender_required": False,
        "registered_sender_status": "not_required",
        "supported_number_types": ["mobile"],
        "price_units_per_segment": 5,
        "verified": True,
    }
    body.update(overrides)
    return body


def go_live(env: LiveEnv) -> tuple[dict[str, str], str]:
    """Operator steps: confirm live for this environment and verify one route. Then a sender."""
    harness = env.harness
    assert harness is not None
    admin, _ = admin_user(harness)
    providers = {
        p["provider"]: p
        for p in harness.client.get("/api/v1/admin/sms/providers", headers=admin).json()["data"]
    }
    harness.sql(
        "update public.provider_configurations set settings = $1::jsonb where provider = 'twilio'",
        f'{{"sender_numbers": ["{POOL_NUMBER}"]}}',
    )
    wrong = harness.client.post(
        f"/api/v1/admin/sms/providers/{providers['twilio']['id']}/activate",
        json={"confirm_environment": "production"},
        headers=admin,
    )
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "environment_mismatch"
    activated = harness.client.post(
        f"/api/v1/admin/sms/providers/{providers['twilio']['id']}/activate",
        json={"confirm_environment": "test"},
        headers=admin,
    )
    assert activated.status_code == 200, activated.text
    put = harness.client.put(
        "/api/v1/admin/sms/capabilities/SG", json=capability_body(), headers=admin
    )
    assert put.status_code == 200, put.text
    headers, user_id = live_user(harness)
    return headers, user_id


def send_live(harness: Harness, headers: dict[str, str], to: str = SG_NUMBER) -> httpx.Response:
    consent = harness.client.put(
        "/api/v1/sms/consents", json={"to": to, "decision": "granted"}, headers=headers
    )
    assert consent.status_code == 200
    return harness.client.post(
        "/api/v1/sms/messages",
        json={"to": to, "body": "Hello from live", "confirmed": True},
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )


def twilio_post(
    harness: Harness, kind: str, fields: dict[str, str], query: str = "", token: str = TOKEN
) -> httpx.Response:
    url = f"{BASE}/api/v1/webhooks/twilio/{kind}" + (f"?{query}" if query else "")
    body = urlencode(fields)
    signature = compute_signature(token, url, parse_form(body.encode()))
    return harness.client.post(
        f"/api/v1/webhooks/twilio/{kind}" + (f"?{query}" if query else ""),
        content=body,
        headers={
            "X-Twilio-Signature": signature,
            "content-type": "application/x-www-form-urlencoded",
        },
    )


def test_live_mode_is_labelled_and_refuses_to_send_until_an_operator_confirms(
    live: LiveEnv,
) -> None:
    harness = live.harness
    assert harness is not None
    headers, _ = live_user(harness)
    status = harness.client.get("/api/v1/sms/status", headers=headers).json()["data"]
    assert (status["mode"], status["provider"], status["is_simulated"]) == ("live", "twilio", False)
    blocked = send_live(harness, headers)
    # The database still has the simulation active: fail loudly, never fall back.
    assert blocked.status_code == 503
    assert blocked.json()["error"]["code"] == "sms_mode_mismatch"
    assert live.calls == []


def test_unverified_routes_are_unavailable_in_live_mode(live: LiveEnv) -> None:
    harness = live.harness
    assert harness is not None
    headers, _ = go_live(live)
    refused = send_live(harness, headers, to="+12025550142")  # US row is unverified
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "route_unverified"
    assert live.calls == []
    quote = harness.client.post(
        "/api/v1/sms/quote", json={"to": "+12025550142", "body": "x"}, headers=headers
    ).json()["data"]
    assert quote["availability"] == "unavailable"
    assert quote["is_simulated"] is False


def test_live_send_goes_to_twilio_and_only_a_signed_callback_marks_delivery(live: LiveEnv) -> None:
    harness = live.harness
    assert harness is not None
    headers, _ = go_live(live)
    queued = send_live(harness, headers)
    assert queued.status_code == 202, queued.text
    data = queued.json()["data"]
    assert data["is_simulated"] is False and data["status"] == "queued"
    assert live.calls == []  # not inside the request handler

    harness.run_worker()
    assert len(live.calls) == 1
    call = live.calls[0]
    assert call["To"] == SG_NUMBER and call["From"] == POOL_NUMBER
    assert call["StatusCallback"].startswith(f"{BASE}/api/v1/webhooks/twilio/status?sms_id=")
    accepted = message(harness, headers, data["id"])
    assert accepted["status"] == "accepted"  # Twilio "queued" is not delivery
    stored = harness.sql(
        "select provider_message_id, is_simulated from public.message_deliveries where message_id = $1",
        uuid.UUID(data["id"]),
    )[0]
    assert stored["provider_message_id"] == live.sids[0] and stored["is_simulated"] is False

    sid = live.sids[0]
    query = call["StatusCallback"].split("?", 1)[1]
    forged = twilio_post(
        harness,
        "status",
        {"MessageSid": sid, "MessageStatus": "delivered"},
        query,
        token="wrong-token",
    )
    assert forged.status_code == 403
    assert message(harness, headers, data["id"])["status"] == "accepted"

    for status in ("sent", "delivered"):
        ok = twilio_post(harness, "status", {"MessageSid": sid, "MessageStatus": status}, query)
        assert ok.status_code == 200, ok.text
    assert message(harness, headers, data["id"])["status"] == "delivered"
    duplicate = twilio_post(
        harness, "status", {"MessageSid": sid, "MessageStatus": "delivered"}, query
    )
    assert duplicate.status_code == 200
    events = harness.sql(
        "select count(*) as n from public.message_delivery_events e join public.message_deliveries d"
        " on d.id = e.delivery_id where d.message_id = $1 and e.normalised_status = 'delivered'",
        uuid.UUID(data["id"]),
    )
    assert events[0]["n"] == 1


def test_live_inbound_reply_is_verified_routed_and_not_labelled_simulated(live: LiveEnv) -> None:
    harness = live.harness
    assert harness is not None
    headers, _ = go_live(live)
    sent = send_live(harness, headers).json()["data"]
    harness.run_worker()
    fields = {"MessageSid": "SMin0001", "From": SG_NUMBER, "To": POOL_NUMBER, "Body": "Salamat po"}

    assert twilio_post(harness, "inbound", fields, token="wrong").status_code == 403
    unsigned = harness.client.post(
        "/api/v1/webhooks/twilio/inbound",
        content=urlencode(fields),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert unsigned.status_code == 403
    assert harness.sql("select 1 from public.messages where body = 'Salamat po'") == []

    ok = twilio_post(harness, "inbound", fields)
    assert ok.status_code == 200
    assert "<Response></Response>" in ok.text
    assert twilio_post(harness, "inbound", fields).status_code == 200  # Twilio retry
    page = harness.client.get(
        f"/api/v1/sms/conversations/{sent['conversation_id']}/messages", headers=headers
    ).json()["data"]
    inbound = [m for m in page["messages"] if m["direction"] == "inbound"]
    assert [m["body"] for m in inbound] == ["Salamat po"]
    assert inbound[0]["is_simulated"] is False


def test_the_simulation_webhook_does_not_exist_in_live_mode(live: LiveEnv) -> None:
    harness = live.harness
    assert harness is not None
    for kind in ("inbound", "status"):
        assert (
            harness.client.post(f"/api/v1/webhooks/mock/{kind}", content=b"{}").status_code == 404
        )
    admin, _ = admin_user(harness)
    simulate = harness.client.post(
        "/api/v1/admin/sms/simulate/inbound",
        json={"from_phone": SG_NUMBER, "to_number": POOL_NUMBER, "body": "x"},
        headers=admin,
    )
    assert simulate.status_code == 403


def test_twilio_rejection_of_the_number_is_permanent_and_not_retried(live: LiveEnv) -> None:
    harness = live.harness
    assert harness is not None
    headers, _ = go_live(live)
    live.reply = (400, {"code": 21211, "message": "invalid"}, {})
    sent = send_live(harness, headers).json()["data"]
    for _ in range(3):
        harness.clock.advance(400)
        harness.run_worker()
    assert len(live.calls) == 1
    failed = message(harness, headers, sent["id"])
    assert failed["status"] == "failed" and failed["failure"]["is_permanent"] is True
    assert failed["failure"]["reason"] == "The phone number is not valid."
    assert "invalid" not in str(failed)  # provider text is never shown


def test_twilio_outage_is_retried_then_succeeds(live: LiveEnv) -> None:
    harness = live.harness
    assert harness is not None
    headers, _ = go_live(live)
    live.reply = (503, {}, {})
    sent = send_live(harness, headers).json()["data"]
    harness.run_worker()
    assert message(harness, headers, sent["id"])["status"] == "retrying"
    live.reply = (201, {}, {})
    harness.clock.advance(60)
    harness.run_worker()
    assert message(harness, headers, sent["id"])["status"] == "accepted"
    assert len(live.calls) == 2  # one failed request, one accepted: the failed one was a 503
    rows = harness.sql(
        "select attempt_number, status from public.message_deliveries where message_id = $1 order by 1",
        uuid.UUID(sent["id"]),
    )
    assert [(r["attempt_number"], r["status"]) for r in rows] == [(1, "failed"), (2, "accepted")]


def test_twilio_credential_error_pauses_dispatch_and_keeps_the_message_queued(
    live: LiveEnv,
) -> None:
    harness = live.harness
    assert harness is not None
    headers, _ = go_live(live)
    live.reply = (401, {"code": 20003}, {})
    sent = send_live(harness, headers).json()["data"]
    harness.run_worker()
    held = message(harness, headers, sent["id"])
    assert held["status"] == "queued"
    assert harness.gateway.engine.dispatch_paused is True
    harness.run_worker()
    assert len(live.calls) == 1  # the circuit stops hammering a broken account
    admin, _ = admin_user(harness)
    data = harness.client.get("/api/v1/admin/sms/monitoring", headers=admin).json()["data"]
    assert data["dispatch_paused_by_configuration_error"] is True

    live.reply = (201, {}, {})
    harness.clock.advance(120)
    harness.run_worker()
    assert message(harness, headers, sent["id"])["status"] == "accepted"


def test_twilio_opt_out_error_records_a_persistent_opt_out(live: LiveEnv) -> None:
    harness = live.harness
    assert harness is not None
    headers, _ = go_live(live)
    live.reply = (400, {"code": 21610}, {})
    send_live(harness, headers)
    harness.run_worker()
    opted = harness.sql("select source, platform_number from public.sms_opt_outs")
    assert [(r["source"], r["platform_number"]) for r in opted] == [("provider_block", None)]
    blocked = send_live(harness, headers)
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "recipient_opted_out"
