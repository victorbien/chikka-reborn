"""Provider-independent AI contract (docs/architecture/ai-architecture.md).

Services depend on AiProvider and these models only. The provider is a plain text-completion
primitive: prompts, parsing and validation belong to the AI module, so swapping the model
(or the vendor) is a configuration change and never touches feature code.
"""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AiProviderName = Literal["mock", "bedrock"]
AiFeature = Literal[
    "suggest_replies", "translate", "rewrite", "tone_adjust", "summarise", "compose", "optimise_sms"
]
AiFailure = Literal["timeout", "throttled", "unavailable", "blocked", "configuration"]


class AiRequest(BaseModel):
    """One completion. `user_content` is structured data (JSON), never raw concatenation."""

    model_config = ConfigDict(frozen=True)

    feature: AiFeature
    system: str = Field(min_length=1)
    user_content: str = Field(min_length=1)
    max_tokens: int = Field(gt=0, le=4000)
    temperature: float = Field(default=0.3, ge=0, le=1)


class AiCompletion(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    model_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class AiProviderError(Exception):
    """Raised by providers. `message` is safe to log: no prompts, content or credentials."""

    def __init__(self, failure: AiFailure, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.failure: AiFailure = failure
        self.message = message
        self.http_status = http_status

    @property
    def is_transient(self) -> bool:
        # Throttling is not retried: asking again immediately makes it worse.
        return self.failure in ("timeout", "unavailable")


class AiProvider(ABC):
    name: AiProviderName
    model_id: str

    @property
    def is_simulated(self) -> bool:
        return self.name == "mock"

    @abstractmethod
    async def complete(self, request: AiRequest) -> AiCompletion:
        """Return the model's text. Raises AiProviderError; never returns partial results."""

    async def aclose(self) -> None:  # noqa: B027 - optional hook
        """Release network resources."""
