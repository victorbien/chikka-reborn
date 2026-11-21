"""The only place a provider is chosen (design section 2.3).

Mode is startup configuration. A live provider that cannot be built raises: there is no code
path that returns the mock when live was requested.
"""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime

from app.core.config import Settings
from app.integrations.sms.base import ProviderError, SmsProvider
from app.integrations.sms.mock import MockSmsProvider, Timeline
from app.integrations.sms.twilio import TwilioSmsProvider


class LiveSmsConfigurationError(RuntimeError):
    """Live SMS was requested but cannot be initialised. Never downgraded to simulation."""


def build_sms_provider(
    settings: Settings,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    timeline: Timeline | None = None,
) -> SmsProvider:
    if settings.sms_provider_mode == "mock":
        secret = (
            settings.sms_mock_webhook_secret.get_secret_value()
            if settings.sms_mock_webhook_secret
            else secrets.token_urlsafe(32)
        )
        return MockSmsProvider(secret=secret, clock=clock, timeline=timeline)

    # Settings already refuse live mode without confirmation, credentials and a public URL.
    if (
        not settings.sms_live_confirmed
        or settings.twilio_account_sid is None
        or settings.twilio_auth_token is None
    ):
        raise LiveSmsConfigurationError("Live SMS is not fully configured")
    try:
        return TwilioSmsProvider(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token.get_secret_value(),
        )
    except ProviderError as exc:
        raise LiveSmsConfigurationError("Live SMS provider could not be initialised") from exc
