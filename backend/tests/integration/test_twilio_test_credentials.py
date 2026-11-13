"""Twilio *test credentials* (opt-in). Never sends a real SMS.

Twilio's test credentials accept the documented "magic" numbers and return realistic API
responses without delivering anything or charging. The test runs only when both variables are
set by a human; in CI and on a fresh checkout it is skipped. See
docs/deployment/sms-live-activation.md.

    TWILIO_TEST_ACCOUNT_SID, TWILIO_TEST_AUTH_TOKEN
"""

import os
import uuid

import pytest

from app.integrations.sms.base import ProviderError, SendRequest
from app.integrations.sms.twilio import TwilioSmsProvider

SID = os.environ.get("TWILIO_TEST_ACCOUNT_SID")
TOKEN = os.environ.get("TWILIO_TEST_AUTH_TOKEN")

pytestmark = pytest.mark.skipif(
    not (SID and TOKEN), reason="Twilio test credentials are not configured"
)

MAGIC_FROM = "+15005550006"  # Twilio: a valid, SMS-capable test sender
MAGIC_TO = "+15005550010"  # Twilio: invalid number


def request(to: str) -> SendRequest:
    return SendRequest(
        to=to, body="Test", sender=MAGIC_FROM, correlation_id=uuid.uuid4(), idempotency_key="k"
    )


async def test_test_credentials_accept_a_valid_message() -> None:
    provider = TwilioSmsProvider(account_sid=SID or "", auth_token=TOKEN or "")
    try:
        result = await provider.send_message(request("+15005550006"))
    finally:
        await provider.aclose()
    assert result.provider_message_id.startswith("SM")
    assert result.mapped_status == "accepted"


async def test_test_credentials_reject_an_invalid_number_as_permanent() -> None:
    provider = TwilioSmsProvider(account_sid=SID or "", auth_token=TOKEN or "")
    try:
        with pytest.raises(ProviderError) as caught:
            await provider.send_message(request(MAGIC_TO))
    finally:
        await provider.aclose()
    assert caught.value.failure_class == "permanent"
