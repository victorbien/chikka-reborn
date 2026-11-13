import base64
import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import pytest

from app.core.config import Settings
from app.integrations.sms.base import ProviderError, SendRequest
from app.integrations.sms.factory import build_sms_provider
from app.integrations.sms.mock import MockSmsProvider, Timeline
from app.integrations.sms.twilio import (
    TwilioSmsProvider,
    compute_signature,
    map_twilio_status,
    parse_form,
)

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def request(to: str = "+12025550142", key: str = "key-1") -> SendRequest:
    return SendRequest(
        to=to, body="Hi", sender="+12025550190", correlation_id=uuid.uuid4(), idempotency_key=key
    )


# -- mock ---------------------------------------------------------------------------------


async def test_mock_sends_nothing_real_and_ids_are_marked_simulated() -> None:
    provider = MockSmsProvider(secret="s", clock=Clock())
    result = await provider.send_message(request())
    assert result.provider_message_id.startswith("SIM-")
    assert result.mapped_status == "accepted"
    assert provider.is_simulated


async def test_mock_callbacks_follow_the_timeline_and_are_signed() -> None:
    clock = Clock()
    provider = MockSmsProvider(secret="s", clock=clock, timeline=Timeline(sent=3, delivered=6))
    await provider.send_message(request())
    assert await provider.pending_callbacks() == []
    clock.now += timedelta(seconds=3)
    (sent,) = await provider.pending_callbacks()
    clock.now += timedelta(seconds=3)
    (delivered,) = await provider.pending_callbacks()
    for callback in (sent, delivered):
        assert await provider.validate_webhook(callback.raw_body, callback.headers, "u")
    event = await provider.parse_status_callback(delivered.raw_body, delivered.headers, {})
    assert event.mapped_status == "delivered"
    assert event.correlation_id is not None


async def test_mock_rejects_tampering_missing_and_stale_signatures() -> None:
    clock = Clock()
    provider = MockSmsProvider(secret="s", clock=clock)
    callback = provider.build_inbound_callback(
        from_phone="+12025550142", to_number="+12025550190", body="hello"
    )
    assert await provider.validate_webhook(callback.raw_body, callback.headers, "u")
    assert not await provider.validate_webhook(callback.raw_body + b" ", callback.headers, "u")
    assert not await provider.validate_webhook(callback.raw_body, {}, "u")
    other = MockSmsProvider(secret="different", clock=clock)
    assert not await other.validate_webhook(callback.raw_body, callback.headers, "u")
    clock.now += timedelta(minutes=10)
    assert not await provider.validate_webhook(callback.raw_body, callback.headers, "u")


@pytest.mark.parametrize(
    ("number", "failure_class", "code"),
    [
        ("+12025550105", "permanent", "SIM-INVALID"),
        ("+12025550104", "transient", "SIM-TRANSIENT"),
        ("+12025550110", "ambiguous", "SIM-TIMEOUT"),
    ],
)
async def test_mock_error_scenarios(number: str, failure_class: str, code: str) -> None:
    provider = MockSmsProvider(secret="s", clock=Clock())
    with pytest.raises(ProviderError) as caught:
        await provider.send_message(request(number))
    assert (caught.value.failure_class, caught.value.code) == (failure_class, code)
    assert provider.sent == []


async def test_mock_transient_then_success_counts_attempts_per_idempotency_key() -> None:
    provider = MockSmsProvider(secret="s", clock=Clock())
    with pytest.raises(ProviderError):
        await provider.send_message(request("+12025550103", "k"))
    assert (await provider.send_message(request("+12025550103", "k"))).provider_message_id
    # A different message starts over.
    with pytest.raises(ProviderError):
        await provider.send_message(request("+12025550103", "other"))


async def test_mock_no_receipt_stops_at_sent_and_status_lookup_agrees() -> None:
    clock = Clock()
    provider = MockSmsProvider(secret="s", clock=clock)
    result = await provider.send_message(request("+12025550107"))
    clock.now += timedelta(days=1)
    callbacks = await provider.pending_callbacks()
    assert len(callbacks) == 1
    snapshot = await provider.get_message_status(result.provider_message_id)
    assert snapshot.mapped_status == "sent"


async def test_mock_out_of_order_and_duplicate_scenarios() -> None:
    clock = Clock()
    provider = MockSmsProvider(secret="s", clock=clock)
    await provider.send_message(request("+12025550109"))
    clock.now += timedelta(minutes=1)
    statuses = [
        (await provider.parse_status_callback(c.raw_body, c.headers, {})).provider_status
        for c in await provider.pending_callbacks()
    ]
    assert statuses == ["delivered", "sent"]

    await provider.send_message(request("+12025550108"))
    clock.now += timedelta(minutes=1)
    keys = [
        (await provider.parse_status_callback(c.raw_body, c.headers, {})).dedupe_key
        for c in await provider.pending_callbacks()
    ]
    assert len(keys) == 3
    assert len(set(keys)) == 2


# -- twilio -------------------------------------------------------------------------------


def twilio(handler: httpx.MockTransport) -> TwilioSmsProvider:
    return TwilioSmsProvider(
        account_sid="ACfake", auth_token="fake-token", client=httpx.AsyncClient(transport=handler)
    )


async def test_twilio_send_success_maps_queued_to_accepted_not_delivered() -> None:
    seen: dict[str, str] = {}

    def handle(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["body"] = req.content.decode()
        return httpx.Response(
            201,
            json={"sid": "SMfake1", "status": "queued", "num_segments": "2", "error_code": None},
        )

    provider = twilio(httpx.MockTransport(handle))
    result = await provider.send_message(
        SendRequest(
            to="+12025550142",
            body="Hi",
            sender="+12025550190",
            correlation_id=uuid.uuid4(),
            idempotency_key="k",
            status_callback_url="https://api.test/cb?sms_id=1",
        )
    )
    assert (result.provider_message_id, result.mapped_status, result.segments_reported) == (
        "SMfake1",
        "accepted",
        2,
    )
    assert "StatusCallback=" in seen["body"]
    assert "Hi" not in str(result.response)


@pytest.mark.parametrize(
    ("status", "payload", "failure_class"),
    [
        (400, {"code": 21211}, "permanent"),
        (400, {"code": 21610}, "permanent"),
        (400, {"code": 99999}, "permanent"),
        (401, {"code": 20003}, "configuration"),
        (429, {}, "transient"),
        (503, {}, "transient"),
    ],
)
async def test_twilio_http_errors_are_classified(
    status: int, payload: dict[str, int], failure_class: str
) -> None:
    provider = twilio(httpx.MockTransport(lambda _r: httpx.Response(status, json=payload)))
    with pytest.raises(ProviderError) as caught:
        await provider.send_message(request())
    assert caught.value.failure_class == failure_class


async def test_twilio_retry_after_is_honoured() -> None:
    transport = httpx.MockTransport(lambda _r: httpx.Response(429, headers={"Retry-After": "42"}))
    with pytest.raises(ProviderError) as caught:
        await twilio(transport).send_message(request())
    assert caught.value.retry_after == 42


async def test_twilio_network_failures_split_into_transient_and_ambiguous() -> None:
    def refuse(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    def stall(_r: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ProviderError) as connect:
        await twilio(httpx.MockTransport(refuse)).send_message(request())
    assert connect.value.failure_class == "transient"
    with pytest.raises(ProviderError) as read:
        await twilio(httpx.MockTransport(stall)).send_message(request())
    assert read.value.failure_class == "ambiguous"


def test_twilio_signature_matches_the_documented_algorithm() -> None:
    # Independent construction of Twilio's documented scheme: URL, then each parameter name
    # followed by its value in alphabetical order, HMAC-SHA1 with the token, base64.
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    params = {
        "To": ["+18005551212"],
        "Digits": ["1234"],
        "CallSid": ["CA1234567890ABCDE"],
        "From": ["+12349013030"],
        "Caller": ["+12349013030"],
    }
    payload = (
        url
        + "CallSid"
        + "CA1234567890ABCDE"
        + "Caller"
        + "+12349013030"
        + "Digits"
        + "1234"
        + "From"
        + "+12349013030"
        + "To"
        + "+18005551212"
    )
    expected = base64.b64encode(
        hmac.new(b"12345", payload.encode(), hashlib.sha1).digest()
    ).decode()
    assert compute_signature("12345", url, params) == expected


async def test_twilio_webhook_validation_uses_raw_form_and_rejects_bad_signatures() -> None:
    provider = twilio(httpx.MockTransport(lambda _r: httpx.Response(200)))
    body = urlencode(
        {"MessageSid": "SM1", "From": "+12025550142", "To": "+12025550190", "Body": "Hi"}
    )
    url = "https://api.test/api/v1/webhooks/twilio/inbound"
    signature = compute_signature("fake-token", url, parse_form(body.encode()))
    assert await provider.validate_webhook(body.encode(), {"X-Twilio-Signature": signature}, url)
    assert not await provider.validate_webhook(body.encode(), {"X-Twilio-Signature": "bad"}, url)
    assert not await provider.validate_webhook(body.encode(), {}, url)
    assert not await provider.validate_webhook(
        body.encode() + b"&x=1", {"X-Twilio-Signature": signature}, url
    )
    assert not await provider.validate_webhook(
        body.encode(), {"X-Twilio-Signature": signature}, url + "/other"
    )


async def test_twilio_parses_inbound_and_status_callbacks() -> None:
    provider = twilio(httpx.MockTransport(lambda _r: httpx.Response(200)))
    inbound = await provider.parse_inbound_message(
        urlencode(
            {"MessageSid": "SM9", "From": "+12025550142", "To": "+12025550190", "Body": "Sige po"}
        ).encode(),
        {},
    )
    assert (inbound.provider_message_id, inbound.body, inbound.dedupe_key) == (
        "SM9",
        "Sige po",
        "SM9",
    )
    correlation = uuid.uuid4()
    status = await provider.parse_status_callback(
        urlencode(
            {"MessageSid": "SM9", "MessageStatus": "undelivered", "ErrorCode": "30003"}
        ).encode(),
        {},
        {"sms_id": str(correlation)},
    )
    assert (status.mapped_status, status.error_code, status.correlation_id) == (
        "undelivered",
        "30003",
        correlation,
    )
    assert map_twilio_status("surprise") is None


async def test_twilio_country_info_reports_price_without_claiming_support() -> None:
    payload = {
        "price_unit": "USD",
        "outbound_sms_prices": [
            {"prices": [{"number_type": "mobile", "current_price": "0.0400"}]},
            {"prices": [{"number_type": "mobile", "current_price": "0.0500"}]},
        ],
    }
    provider = twilio(httpx.MockTransport(lambda _r: httpx.Response(200, json=payload)))
    info = await provider.get_country_capabilities("ph")
    assert str(info.outbound_price_per_segment) == "0.0500"
    assert info.inbound_supported is None


# -- factory ------------------------------------------------------------------------------


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg, arg-type]


def test_factory_builds_mock_by_default() -> None:
    provider = build_sms_provider(settings())
    assert (provider.name, provider.mode) == ("mock", "simulation")


def test_live_mode_refuses_to_start_without_credentials_or_confirmation() -> None:
    with pytest.raises(ValueError, match="TWILIO_ACCOUNT_SID"):
        settings(sms_provider_mode="live", sms_live_confirmed=True)


def test_factory_builds_twilio_only_when_fully_configured() -> None:
    provider = build_sms_provider(
        settings(
            sms_provider_mode="live",
            sms_live_confirmed=True,
            twilio_account_sid="ACfake",
            twilio_auth_token="fake-token",
            sms_public_base_url="https://api.test",
        )
    )
    assert (provider.name, provider.mode) == ("twilio", "live")
