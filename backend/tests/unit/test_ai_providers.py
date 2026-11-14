import json
import logging

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.integrations.ai.base import AiProviderError, AiRequest
from app.integrations.ai.bedrock import BedrockAiProvider
from app.integrations.ai.factory import AiConfigurationError, build_ai_provider
from app.integrations.ai.mock import MockAiProvider

API_KEY = "fake-bedrock-key-for-tests"  # fake, never a real credential


def request() -> AiRequest:
    return AiRequest(
        feature="translate",
        system="system prompt",
        user_content=json.dumps({"text": "private words"}),
        max_tokens=100,
    )


def bedrock(handler: httpx.MockTransport | None = None, **overrides: object) -> BedrockAiProvider:
    return BedrockAiProvider(
        region="ap-southeast-1",
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        api_key=API_KEY,
        timeout_seconds=5,
        client=httpx.AsyncClient(transport=handler) if handler else None,
        **overrides,  # type: ignore[arg-type]
    )


def ok_body(text: str = '{"text": "Hola"}') -> dict[str, object]:
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 12, "outputTokens": 5},
    }


async def test_bedrock_sends_a_converse_request_and_returns_text_and_usage() -> None:
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=ok_body())

    completion = await bedrock(httpx.MockTransport(handler)).complete(request())

    assert completion.text == '{"text": "Hola"}'
    assert (completion.input_tokens, completion.output_tokens) == (12, 5)
    assert seen["url"] == (
        "https://bedrock-runtime.ap-southeast-1.amazonaws.com/model/"
        "anthropic.claude-3-haiku-20240307-v1%3A0/converse"
    )
    assert seen["auth"] == f"Bearer {API_KEY}"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["system"] == [{"text": "system prompt"}]
    assert body["inferenceConfig"] == {"maxTokens": 100, "temperature": 0.3}


@pytest.mark.parametrize(
    ("status", "failure"),
    [
        (429, "throttled"),
        (408, "timeout"),
        (504, "timeout"),
        (500, "unavailable"),
        (503, "unavailable"),
        (400, "unavailable"),
        (403, "configuration"),
        (401, "configuration"),
    ],
)
async def test_bedrock_http_errors_are_classified(status: int, failure: str) -> None:
    transport = httpx.MockTransport(lambda _r: httpx.Response(status, json={"message": "nope"}))

    with pytest.raises(AiProviderError) as caught:
        await bedrock(transport).complete(request())

    assert caught.value.failure == failure
    assert API_KEY not in caught.value.message


async def test_bedrock_network_errors_are_classified() -> None:
    def timeout(_r: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    def refused(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(AiProviderError) as slow:
        await bedrock(httpx.MockTransport(timeout)).complete(request())
    with pytest.raises(AiProviderError) as down:
        await bedrock(httpx.MockTransport(refused)).complete(request())

    assert (slow.value.failure, down.value.failure) == ("timeout", "unavailable")
    assert slow.value.is_transient and not AiProviderError("throttled", "x").is_transient


async def test_bedrock_guardrail_stop_is_a_blocked_failure() -> None:
    body = {**ok_body(), "stopReason": "guardrail_intervened"}
    transport = httpx.MockTransport(lambda _r: httpx.Response(200, json=body))

    with pytest.raises(AiProviderError) as caught:
        await bedrock(transport).complete(request())

    assert caught.value.failure == "blocked"


@pytest.mark.parametrize("body", [{}, {"output": {}}, {"output": {"message": {"content": "x"}}}])
async def test_bedrock_malformed_responses_are_unavailable(body: dict[str, object]) -> None:
    transport = httpx.MockTransport(lambda _r: httpx.Response(200, json=body))

    with pytest.raises(AiProviderError) as caught:
        await bedrock(transport).complete(request())

    assert caught.value.failure == "unavailable"


async def test_bedrock_never_logs_prompts_completions_or_the_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    transport = httpx.MockTransport(lambda _r: httpx.Response(500, json={"message": "private"}))

    with pytest.raises(AiProviderError):
        await bedrock(transport).complete(request())

    logged = " ".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    assert API_KEY not in logged and "private words" not in logged and "system prompt" not in logged


def test_bedrock_needs_every_setting() -> None:
    with pytest.raises(AiProviderError):
        BedrockAiProvider(region="", model_id="m", api_key="k", timeout_seconds=5)


# -- factory and configuration -----------------------------------------------------------------


def make_settings(**values: object) -> Settings:
    return Settings(_env_file=None, app_env="test", **values)  # type: ignore[call-arg]


def test_default_mode_is_the_mock_and_calls_nothing_external() -> None:
    provider = build_ai_provider(make_settings())

    assert isinstance(provider, MockAiProvider) and provider.is_simulated


def test_bedrock_mode_without_configuration_fails_at_startup_not_to_the_mock() -> None:
    with pytest.raises(ValidationError, match="BEDROCK_REGION, BEDROCK_MODEL_ID, BEDROCK_API_KEY"):
        make_settings(ai_provider_mode="bedrock")


def test_bedrock_mode_builds_the_bedrock_provider() -> None:
    settings = make_settings(
        ai_provider_mode="bedrock",
        bedrock_region="ap-southeast-1",
        bedrock_model_id="model-1",
        bedrock_api_key=SecretStr(API_KEY),
    )

    provider = build_ai_provider(settings)

    assert isinstance(provider, BedrockAiProvider) and not provider.is_simulated
    assert provider.model_id == "model-1"


def test_factory_refuses_to_fall_back_when_settings_were_bypassed() -> None:
    settings = make_settings().model_copy(update={"ai_provider_mode": "bedrock"})

    with pytest.raises(AiConfigurationError):
        build_ai_provider(settings)


def test_blank_bedrock_values_count_as_unset() -> None:
    settings = make_settings(bedrock_region="  ", bedrock_api_key="")

    assert settings.bedrock_region is None and settings.bedrock_api_key is None


# -- mock provider -----------------------------------------------------------------------------


async def test_mock_replays_the_script_then_falls_back_to_deterministic_defaults() -> None:
    provider = MockAiProvider(script=["first", AiProviderError("timeout", "slow")])

    assert (await provider.complete(request())).text == "first"
    with pytest.raises(AiProviderError):
        await provider.complete(request())
    demo = AiRequest(
        feature="translate",
        system="s",
        user_content=json.dumps({"text": "Hello", "target_language": "Spanish"}),
        max_tokens=10,
    )
    assert json.loads((await provider.complete(demo)).text) == {"text": "[Spanish] Hello"}
    assert len(provider.calls) == 3
