"""SMTP adapter using the standard library (no new dependency).

smtplib is blocking, so each send runs in a worker thread. Credentials come from configuration
and are never logged. Rejected recipients are permanent failures; connection and server errors
are transient.
"""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage as MimeMessage

from app.integrations.email.base import EmailError, EmailMessage, EmailProvider

logger = logging.getLogger(__name__)


class SmtpEmailProvider(EmailProvider):
    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        username: str | None,
        password: str | None,
        starttls: bool,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not host or not sender:
            raise EmailError("SMTP host and sender address are required", permanent=True)
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._starttls = starttls
        self._timeout = timeout_seconds

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_blocking, message)

    def _send_blocking(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject.replace("\r", " ").replace("\n", " ")
        mime.set_content(message.text)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
                if self._starttls:
                    client.starttls(context=ssl.create_default_context())
                if self._username and self._password:
                    client.login(self._username, self._password)
                client.send_message(mime)
        except smtplib.SMTPRecipientsRefused as exc:
            raise EmailError("SMTP rejected the recipient", permanent=True) from exc
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("smtp send failed", extra={"error_type": type(exc).__name__})
            raise EmailError("SMTP send failed") from exc
