import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_ai_service
from app.integrations.ai.base import AiProviderError
from app.modules.chat.context import ContextLine
from tests.support.ai import CONVERSATION_ID, USER_ID, AiHarness, build_harness


@pytest.fixture
def harness(app: FastAPI) -> AiHarness:
    built = build_harness()
    built.chat.lines = [ContextLine(from_me=False, text="Are you free tomorrow?")]
    app.dependency_overrides[get_ai_service] = lambda: built.service
    return built


@pytest.fixture
def auth(make_token: Callable[..., str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=str(USER_ID))}"}


def reply(**fields: object) -> str:
    return json.dumps(fields)


def test_every_endpoint_requires_a_signed_in_user(client: TestClient, harness: AiHarness) -> None:
    for method, path in [
        ("get", "/api/v1/ai/status"),
        ("put", "/api/v1/ai/settings"),
        ("post", "/api/v1/ai/translate"),
        ("post", "/api/v1/ai/suggest-replies"),
        ("post", "/api/v1/ai/rewrite"),
        ("post", "/api/v1/ai/optimise-sms"),
        ("post", "/api/v1/ai/summarise"),
        ("post", "/api/v1/ai/compose"),
        ("post", f"/api/v1/ai/assistance/{CONVERSATION_ID}/decision"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "not_authenticated"
    assert harness.provider.calls == []


def test_translate_returns_the_enveloped_draft(
    client: TestClient, harness: AiHarness, auth: dict[str, str]
) -> None:
    harness.provider.queue(reply(text="Kumusta"))

    response = client.post(
        "/api/v1/ai/translate",
        headers=auth,
        json={"text": "Hello", "target_language": "fil", "source_language": "en"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"]
    assert body["data"]["translated_text"] == "Kumusta"
    assert body["data"]["simulated"] is True


def test_the_full_draft_then_decision_round_trip(
    client: TestClient, harness: AiHarness, auth: dict[str, str]
) -> None:
    harness.provider.queue(reply(suggestions=["Yes, I am!", "Not really"]))

    drafted = client.post(
        "/api/v1/ai/suggest-replies",
        headers=auth,
        json={"conversation_id": str(CONVERSATION_ID), "count": 2},
    ).json()["data"]
    decided = client.post(
        f"/api/v1/ai/assistance/{drafted['assistance_id']}/decision",
        headers=auth,
        json={"decision": "accepted"},
    )

    assert drafted["suggestions"] == ["Yes, I am!", "Not really"]
    assert decided.status_code == 200 and decided.json()["data"]["decision"] == "accepted"


def test_an_unknown_assistance_id_is_not_found(
    client: TestClient, harness: AiHarness, auth: dict[str, str]
) -> None:
    response = client.post(
        f"/api/v1/ai/assistance/{CONVERSATION_ID}/decision",
        headers=auth,
        json={"decision": "dismissed"},
    )

    assert response.status_code == 404


def test_provider_failure_is_a_502_envelope_without_provider_details(
    client: TestClient, harness: AiHarness, auth: dict[str, str]
) -> None:
    harness.provider.queue(
        AiProviderError("unavailable", "aws secret detail"),
        AiProviderError("unavailable", "aws secret detail"),
    )

    response = client.post(
        "/api/v1/ai/rewrite", headers=auth, json={"text": "hey", "instruction": "shorten"}
    )

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "ai_unavailable"
    assert "aws secret detail" not in response.text


def test_not_opted_in_is_a_403_and_the_model_is_never_called(
    client: TestClient, harness: AiHarness, auth: dict[str, str]
) -> None:
    harness.state.user_enabled[USER_ID] = False

    response = client.post(
        "/api/v1/ai/compose", headers=auth, json={"prompt": "Tell my friend I am late"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ai_not_enabled"
    assert harness.provider.calls == []


def test_status_and_settings_toggle(
    client: TestClient, harness: AiHarness, auth: dict[str, str]
) -> None:
    off = client.put("/api/v1/ai/settings", headers=auth, json={"enabled": False})
    status = client.get("/api/v1/ai/status", headers=auth)

    assert off.json()["data"]["enabled"] is False
    assert status.json()["data"]["enabled"] is False
    assert status.json()["data"]["available"] is True


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("translate", {"text": "Hi", "target_language": "xx"}),
        ("translate", {"text": " ", "target_language": "es"}),
        ("translate", {"text": "x" * 1601, "target_language": "es"}),
        ("translate", {"text": "Hi", "target_language": "es", "send": True}),
        ("rewrite", {"text": "Hi", "instruction": "make_evil"}),
        ("rewrite", {"text": "Hi", "instruction": "adjust_tone"}),
        ("optimise-sms", {"text": "Hi", "max_segments": 0}),
        ("optimise-sms", {"text": "Hi", "max_segments": 11}),
        ("suggest-replies", {"conversation_id": "not-a-uuid"}),
        ("suggest-replies", {"conversation_id": str(CONVERSATION_ID), "count": 6}),
        ("summarise", {"conversation_id": str(CONVERSATION_ID), "message_count": 51}),
        ("compose", {"prompt": "x" * 301}),
        ("compose", {"prompt": "Hi", "context": ["a"] * 6}),
    ],
)
def test_invalid_input_is_rejected_before_any_model_call(
    client: TestClient,
    harness: AiHarness,
    auth: dict[str, str],
    path: str,
    payload: dict[str, Any],
) -> None:
    response = client.post(f"/api/v1/ai/{path}", headers=auth, json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert harness.provider.calls == []


def test_the_ai_module_has_no_way_to_send_a_message() -> None:
    from app.modules.ai.router import router

    assert not [r for r in router.routes if "send" in getattr(r, "path", "")]
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("app/modules/ai").glob("*.py")
    )
    for forbidden in ("send_message", "SmsService", "SmsProvider", "sms.service", "chat.service"):
        assert forbidden not in sources, forbidden
