"""Amazon Bedrock adapter (Converse API over HTTPS).

Only this file knows Bedrock's wire format. Credentials are a backend-only Bedrock API key.
Prompts, completions and the key are never logged; failures log the status and error type only.
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.integrations.ai.base import AiCompletion, AiProvider, AiProviderError, AiRequest

logger = logging.getLogger(__name__)

# Converse stop reasons that mean the model's safety layer, not the user, ended the answer.
_BLOCKED_STOP_REASONS = frozenset({"guardrail_intervened", "content_filtered"})


class BedrockAiProvider(AiProvider):
    name = "bedrock"

    def __init__(
        self,
        *,
        region: str,
        model_id: str,
        api_key: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not (region and model_id and api_key):
            raise AiProviderError("configuration", "Bedrock is not fully configured")
        self.model_id = model_id
        self._url = (
            f"https://bedrock-runtime.{region}.amazonaws.com/model/{quote(model_id, safe='')}"
            "/converse"
        )
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(self, request: AiRequest) -> AiCompletion:
        payload: dict[str, Any] = {
            "system": [{"text": request.system}],
            "messages": [{"role": "user", "content": [{"text": request.user_content}]}],
            "inferenceConfig": {
                "maxTokens": request.max_tokens,
                "temperature": request.temperature,
            },
        }
        try:
            response = await self._client.post(self._url, headers=self._headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("bedrock timeout", extra={"feature": request.feature})
            raise AiProviderError("timeout", "Bedrock did not answer in time") from exc
        except httpx.HTTPError as exc:
            logger.warning("bedrock unreachable", extra={"error_type": type(exc).__name__})
            raise AiProviderError("unavailable", "Bedrock is unreachable") from exc

        if response.status_code >= 400:
            raise self._error_for(response.status_code)
        return self._parse(response)

    @staticmethod
    def _error_for(status: int) -> AiProviderError:
        logger.warning("bedrock error", extra={"status_code": status})
        if status == 429:
            return AiProviderError(
                "throttled", "Bedrock is throttling requests", http_status=status
            )
        if status in (408, 504):
            return AiProviderError("timeout", "Bedrock timed out", http_status=status)
        if status in (401, 403):
            # A credential or access problem is an operator issue, not a transient one.
            return AiProviderError(
                "configuration", "Bedrock refused the credentials", http_status=status
            )
        return AiProviderError("unavailable", "Bedrock request failed", http_status=status)

    def _parse(self, response: httpx.Response) -> AiCompletion:
        try:
            body = response.json()
            if body.get("stopReason") in _BLOCKED_STOP_REASONS:
                raise AiProviderError("blocked", "The model declined this request")
            parts = body["output"]["message"]["content"]
            if not isinstance(parts, list):
                raise TypeError("content is not a list")
            text = "".join(part["text"] for part in parts if "text" in part)
            usage = body.get("usage") or {}
            return AiCompletion(
                text=text,
                model_id=self.model_id,
                input_tokens=_as_int(usage.get("inputTokens")),
                output_tokens=_as_int(usage.get("outputTokens")),
            )
        except AiProviderError:
            raise
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning("bedrock malformed response", extra={"error_type": type(exc).__name__})
            raise AiProviderError("unavailable", "Bedrock returned an unreadable response") from exc


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None
