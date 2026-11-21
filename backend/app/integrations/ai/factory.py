"""The only place an AI provider is chosen.

Mode is startup configuration. Bedrock that cannot be built raises: no code path returns the
mock when Bedrock was requested.
"""

from app.core.config import Settings
from app.integrations.ai.base import AiProvider, AiProviderError
from app.integrations.ai.bedrock import BedrockAiProvider
from app.integrations.ai.mock import MockAiProvider


class AiConfigurationError(RuntimeError):
    """Bedrock was requested but cannot be initialised. Never downgraded to the mock."""


def build_ai_provider(settings: Settings) -> AiProvider:
    if settings.ai_provider_mode == "mock":
        return MockAiProvider()
    if (
        settings.bedrock_region is None
        or settings.bedrock_model_id is None
        or settings.bedrock_api_key is None
    ):
        raise AiConfigurationError("Bedrock is not fully configured")
    try:
        return BedrockAiProvider(
            region=settings.bedrock_region,
            model_id=settings.bedrock_model_id,
            api_key=settings.bedrock_api_key.get_secret_value(),
            timeout_seconds=settings.ai_timeout_seconds,
        )
    except AiProviderError as exc:
        raise AiConfigurationError("Bedrock could not be initialised") from exc
