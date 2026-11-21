"""The only place an email provider is chosen. SMTP that cannot be built raises; it never
becomes the mock."""

from app.core.config import Settings
from app.integrations.email.base import EmailError, EmailProvider
from app.integrations.email.mock import MockEmailProvider
from app.integrations.email.smtp import SmtpEmailProvider


class EmailConfigurationError(RuntimeError):
    """SMTP was requested but cannot be initialised."""


def build_email_provider(settings: Settings) -> EmailProvider:
    if settings.email_provider_mode == "mock":
        return MockEmailProvider()
    if settings.smtp_host is None or settings.email_from_address is None:
        raise EmailConfigurationError("SMTP is not fully configured")
    try:
        return SmtpEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            sender=settings.email_from_address,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            starttls=settings.smtp_starttls,
        )
    except EmailError as exc:
        raise EmailConfigurationError("SMTP could not be initialised") from exc
