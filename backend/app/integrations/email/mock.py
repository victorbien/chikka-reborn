"""Mock email provider: nothing leaves the machine. Tests read `outbox` and can script failures."""

from collections import deque
from collections.abc import Iterable

from app.integrations.email.base import EmailError, EmailMessage, EmailProvider


class MockEmailProvider(EmailProvider):
    name = "mock"

    def __init__(self, *, failures: Iterable[EmailError] = ()) -> None:
        self._failures: deque[EmailError] = deque(failures)
        self.outbox: list[EmailMessage] = []

    def fail_next(self, *errors: EmailError) -> None:
        self._failures.extend(errors)

    async def send(self, message: EmailMessage) -> None:
        if self._failures:
            raise self._failures.popleft()
        self.outbox.append(message)
