import smtplib
from datetime import UTC, datetime, time
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.email.base import EmailError, EmailMessage
from app.integrations.email.factory import EmailConfigurationError, build_email_provider
from app.integrations.email.mock import MockEmailProvider
from app.integrations.email.smtp import SmtpEmailProvider
from app.modules.notifications.preferences import (
    DEFAULTS,
    MANDATORY_IN_APP,
    TYPES,
    Preferences,
    in_quiet_hours,
    overrides_for,
)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 14, hour, minute, tzinfo=UTC)


# -- preferences ---------------------------------------------------------------------------------


def test_every_type_has_a_default_for_every_channel() -> None:
    assert set(DEFAULTS) == set(TYPES)
    assert all(set(channels) == {"in_app", "push", "email"} for channels in DEFAULTS.values())
    assert all(DEFAULTS[kind]["in_app"] for kind in TYPES)


def test_overrides_win_over_defaults_but_mandatory_in_app_never_turns_off() -> None:
    prefs = Preferences(
        overrides={"new_message.email": True, "new_message.push": False, "system.in_app": False}
    )

    assert prefs.wants("new_message", "email") is True
    assert prefs.wants("new_message", "push") is False
    assert prefs.wants("contact_request", "email") is False  # default
    assert prefs.wants("system", "in_app") is True  # locked, whatever is stored
    assert {"sms_failed", "system", "security"} == set(MANDATORY_IN_APP)


def test_only_message_notifications_depend_on_previews() -> None:
    off, on = Preferences(), Preferences(show_previews=True)

    assert off.keeps_body("new_message") is False and on.keeps_body("new_message") is True
    assert off.keeps_body("sms_inbound") is False
    assert off.keeps_body("system") is True and off.keeps_body("low_balance") is True


def test_overrides_for_keeps_only_deviations() -> None:
    matrix = {
        "new_message": {"in_app": True, "push": False, "email": False},
        "security": {"in_app": True, "push": True, "email": True},
    }

    assert overrides_for(matrix) == {"new_message.push": False}


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (at(21, 59), False),
        (at(22, 0), True),  # start is inclusive
        (at(3), True),  # after midnight
        (at(6, 59), True),
        (at(7, 0), False),  # end is exclusive
        (at(12), False),
    ],
)
def test_quiet_hours_may_wrap_midnight(now: datetime, expected: bool) -> None:
    assert in_quiet_hours(now, "UTC", time(22, 0), time(7, 0)) is expected


def test_quiet_hours_use_the_users_time_zone() -> None:
    # 14:00 UTC is 22:00 in Manila: inside 22:00-07:00 there, outside in UTC.
    assert in_quiet_hours(at(14), "Asia/Manila", time(22, 0), time(7, 0)) is True
    assert in_quiet_hours(at(14), "UTC", time(22, 0), time(7, 0)) is False
    assert (
        in_quiet_hours(at(14), "Not/AZone", time(22, 0), time(7, 0)) is False
    )  # falls back to UTC


@pytest.mark.parametrize(("start", "end"), [(None, None), (time(8), time(8)), (time(8), None)])
def test_no_quiet_hours_when_unset_or_empty(start: time | None, end: time | None) -> None:
    assert in_quiet_hours(at(8), "UTC", start, end) is False


# -- email providers -----------------------------------------------------------------------------


def settings(**values: object) -> Settings:
    return Settings(_env_file=None, app_env="test", **values)  # type: ignore[call-arg]


async def test_the_mock_email_provider_records_and_can_fail_on_demand() -> None:
    provider = MockEmailProvider()
    message = EmailMessage(to="a@example.com", subject="Hi", text="Body")

    await provider.send(message)
    provider.fail_next(EmailError("down"))
    with pytest.raises(EmailError):
        await provider.send(message)
    await provider.send(message)

    assert provider.outbox == [message, message] and provider.is_simulated is True


def test_default_email_mode_is_the_mock() -> None:
    assert isinstance(build_email_provider(settings()), MockEmailProvider)


def test_smtp_mode_without_configuration_fails_at_startup() -> None:
    with pytest.raises(ValidationError, match="SMTP_HOST, EMAIL_FROM_ADDRESS"):
        settings(email_provider_mode="smtp")


def test_smtp_mode_builds_the_smtp_provider_and_never_falls_back() -> None:
    built = build_email_provider(
        settings(
            email_provider_mode="smtp",
            smtp_host="smtp.example.test",
            email_from_address="no-reply@example.test",
        )
    )
    bypassed = settings().model_copy(update={"email_provider_mode": "smtp"})

    assert isinstance(built, SmtpEmailProvider) and built.is_simulated is False
    with pytest.raises(EmailConfigurationError):
        build_email_provider(bypassed)


def smtp() -> SmtpEmailProvider:
    return SmtpEmailProvider(
        host="smtp.example.test",
        port=587,
        sender="no-reply@example.test",
        username="user",
        password="fake-password",  # fake, never a real credential
        starttls=True,
    )


async def test_smtp_sends_a_plain_text_message_with_starttls_and_login() -> None:
    client = MagicMock()
    with patch("smtplib.SMTP") as factory:
        factory.return_value.__enter__.return_value = client
        await smtp().send(EmailMessage(to="a@example.com", subject="Two\nlines", text="Hello"))

    client.starttls.assert_called_once()
    client.login.assert_called_once_with("user", "fake-password")
    sent = client.send_message.call_args.args[0]
    assert sent["To"] == "a@example.com" and sent["From"] == "no-reply@example.test"
    assert "\n" not in sent["Subject"]  # no header injection through the subject
    assert sent.get_content().strip() == "Hello"


@pytest.mark.parametrize(
    ("error", "permanent"),
    [
        (smtplib.SMTPRecipientsRefused({}), True),
        (smtplib.SMTPServerDisconnected("gone"), False),
        (OSError("unreachable"), False),
    ],
)
async def test_smtp_failures_are_classified_without_leaking_details(
    error: Exception, permanent: bool
) -> None:
    with patch("smtplib.SMTP", side_effect=error), pytest.raises(EmailError) as caught:
        await smtp().send(EmailMessage(to="a@example.com", subject="Hi", text="Body"))

    assert caught.value.permanent is permanent
    assert "a@example.com" not in caught.value.message
