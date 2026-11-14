"""Provider-independent email contract for notification emails.

Services depend on EmailProvider and EmailMessage only. A provider raises EmailError; its
message is safe to log (no recipient address, no body, no credentials).
"""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict

EmailProviderName = Literal["mock", "smtp"]


class EmailMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    to: str
    subject: str
    text: str


class EmailError(Exception):
    """`permanent` means retrying cannot help (for example the address was rejected)."""

    def __init__(self, message: str, *, permanent: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.permanent = permanent


class EmailProvider(ABC):
    name: EmailProviderName

    @property
    def is_simulated(self) -> bool:
        return self.name == "mock"

    @abstractmethod
    async def send(self, message: EmailMessage) -> None:
        """Deliver one email. Raises EmailError. Returning means the provider accepted it."""

    async def aclose(self) -> None:  # noqa: B027 - optional hook
        """Release network resources."""
