"""Module F: the AI assistant against the real database, with the mock AI provider.

The assistant is opt-in, drafts only, reads conversation text through the chat module without
marking anything delivered or read, and stores metadata only.
"""

import json
import uuid
from collections.abc import Iterator
from typing import Any, cast

import pytest

from app.integrations.ai.mock import MockAiProvider
from tests.flows.conftest import Harness
from tests.flows.test_chat import open_conversation, send
from tests.flows.test_contacts import Person, befriend, make_person

API = "/api/v1/ai"
PRIVATE_EMAIL = "juan.delacruz@example.com"
PRIVATE_NUMBER = "+63 917 123 4567"


def provider(harness: Harness) -> MockAiProvider:
    return cast(MockAiProvider, harness.client.app.state.providers.ai)  # type: ignore[attr-defined]


@pytest.fixture
def restore_platform_settings(harness: Harness) -> Iterator[None]:
    yield
    harness.sql("update public.system_settings set value = 'true'::jsonb where key = 'ai_enabled'")
    harness.sql(
        "update public.system_settings set value = '30'::jsonb where key = 'ai_user_limit_per_hour'"
    )


def enable(harness: Harness, person: Person) -> None:
    response = harness.client.put(f"{API}/settings", json={"enabled": True}, headers=person.headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["enabled"] is True


def chatting(harness: Harness) -> tuple[Person, Person, str]:
    alice, bob = make_person(harness, "Alice"), make_person(harness, "Bob")
    befriend(harness, alice, bob)
    conversation_id = str(open_conversation(harness, alice, bob)["id"])
    assert send(harness, bob, conversation_id, "Are you free tomorrow?").status_code in (200, 201)
    return alice, bob, conversation_id


def test_ai_is_off_by_default_and_consent_is_audited(harness: Harness) -> None:
    alice = make_person(harness, "Alice")

    status = harness.client.get(f"{API}/status", headers=alice.headers).json()["data"]
    blocked = harness.client.post(
        f"{API}/translate",
        json={"text": "Hello", "target_language": "es"},
        headers=alice.headers,
    )

    assert status["available"] is True and status["enabled"] is False
    assert status["simulated"] is True
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "ai_not_enabled"
    assert provider(harness).calls == []

    enable(harness, alice)
    assert harness.profile(alice.id)["ai_enabled"] is True
    audit = harness.sql(
        "select action, category from public.audit_logs where actor_id = $1 and action like 'ai.%'",
        uuid.UUID(alice.id),
    )
    assert [(r["action"], r["category"]) for r in audit] == [("ai.enabled", "consent")]


def test_translate_stores_metadata_but_never_the_text(harness: Harness) -> None:
    alice = make_person(harness, "Alice")
    enable(harness, alice)
    provider(harness).queue(json.dumps({"text": "Kumusta, mundo"}))

    response = harness.client.post(
        f"{API}/translate",
        json={"text": "Hello world, this is private", "target_language": "fil"},
        headers=alice.headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["translated_text"] == "Kumusta, mundo"
    (row,) = harness.sql(
        "select * from public.ai_assistance_logs where id = $1", uuid.UUID(data["assistance_id"])
    )
    assert (row["feature"], row["outcome"], row["language"]) == ("translate", "success", "fil")
    assert row["user_decision"] == "pending"
    assert row["input_text"] is None and row["output_text"] is None
    assert row["output_hash"] and row["latency_ms"] is not None


def test_suggest_replies_reads_chat_text_without_side_effects_and_masks_it(
    harness: Harness,
) -> None:
    alice, bob, conversation_id = chatting(harness)
    send(harness, bob, conversation_id, f"Call {PRIVATE_NUMBER} or mail {PRIVATE_EMAIL}")
    enable(harness, alice)
    provider(harness).queue(json.dumps({"suggestions": ["Yes, free!", "Sorry, busy"]}))
    before = harness.sql("select status, count(*) n from public.message_deliveries group by 1")
    messages_before = harness.sql("select count(*) n from public.messages")[0]["n"]

    response = harness.client.post(
        f"{API}/suggest-replies",
        json={"conversation_id": conversation_id, "count": 2},
        headers=alice.headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["suggestions"] == ["Yes, free!", "Sorry, busy"]
    sent = provider(harness).calls[-1].user_content
    assert "Are you free tomorrow?" in sent
    assert "917" not in sent and PRIVATE_EMAIL not in sent
    assert "Alice" not in sent and "Bob" not in sent and alice.id not in sent
    # Drafts only: nothing was sent, and reading context did not mark messages delivered.
    assert harness.sql("select count(*) n from public.messages")[0]["n"] == messages_before
    after = harness.sql("select status, count(*) n from public.message_deliveries group by 1")
    assert [(r["status"], r["n"]) for r in after] == [(r["status"], r["n"]) for r in before]


def test_decision_is_recorded_for_the_owner_only(harness: Harness) -> None:
    alice, bob, conversation_id = chatting(harness)
    enable(harness, alice)
    enable(harness, bob)
    provider(harness).queue(json.dumps({"suggestions": ["Sure"]}))
    drafted = harness.client.post(
        f"{API}/suggest-replies", json={"conversation_id": conversation_id}, headers=alice.headers
    ).json()["data"]
    url = f"{API}/assistance/{drafted['assistance_id']}/decision"

    stranger = harness.client.post(url, json={"decision": "accepted"}, headers=bob.headers)
    owner = harness.client.post(url, json={"decision": "edited"}, headers=alice.headers)

    assert stranger.status_code == 404
    assert owner.status_code == 200
    (row,) = harness.sql(
        "select user_decision from public.ai_assistance_logs where id = $1",
        uuid.UUID(drafted["assistance_id"]),
    )
    assert row["user_decision"] == "edited"


def test_a_non_member_cannot_use_someone_elses_conversation(harness: Harness) -> None:
    _alice, _bob, conversation_id = chatting(harness)
    mallory = make_person(harness, "Mallory")
    enable(harness, mallory)

    for path, payload in (
        ("suggest-replies", {"conversation_id": conversation_id}),
        ("summarise", {"conversation_id": conversation_id}),
    ):
        response = harness.client.post(f"{API}/{path}", json=payload, headers=mallory.headers)
        assert response.status_code == 404, path

    assert provider(harness).calls == []


def test_a_conversation_with_ai_switched_off_is_not_sent_to_the_model(harness: Harness) -> None:
    alice, _bob, conversation_id = chatting(harness)
    enable(harness, alice)
    harness.sql(
        "update public.conversation_members set ai_enabled = false "
        "where conversation_id = $1 and user_id = $2",
        uuid.UUID(conversation_id),
        uuid.UUID(alice.id),
    )

    response = harness.client.post(
        f"{API}/summarise", json={"conversation_id": conversation_id}, headers=alice.headers
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ai_disabled_for_conversation"
    assert provider(harness).calls == []


def test_cleared_history_is_not_summarised(harness: Harness) -> None:
    alice, _bob, conversation_id = chatting(harness)
    enable(harness, alice)
    harness.sql(
        "update public.conversation_members set cleared_before_seq = 1000 "
        "where conversation_id = $1 and user_id = $2",
        uuid.UUID(conversation_id),
        uuid.UUID(alice.id),
    )

    response = harness.client.post(
        f"{API}/summarise", json={"conversation_id": conversation_id}, headers=alice.headers
    )

    assert response.status_code == 422 and response.json()["error"]["code"] == "no_context"
    assert provider(harness).calls == []


@pytest.mark.usefixtures("restore_platform_settings")
def test_admin_kill_switch_and_hourly_limit_come_from_system_settings(harness: Harness) -> None:
    alice = make_person(harness, "Alice")
    enable(harness, alice)
    body: dict[str, Any] = {"text": "Hello", "target_language": "es"}

    harness.sql("update public.system_settings set value = 'false'::jsonb where key = 'ai_enabled'")
    off = harness.client.post(f"{API}/translate", json=body, headers=alice.headers)
    status = harness.client.get(f"{API}/status", headers=alice.headers).json()["data"]
    harness.sql("update public.system_settings set value = 'true'::jsonb where key = 'ai_enabled'")

    assert off.status_code == 503 and off.json()["error"]["code"] == "ai_disabled_by_admin"
    assert status["available"] is False

    harness.sql(
        "update public.system_settings set value = '1'::jsonb where key = 'ai_user_limit_per_hour'"
    )
    first = harness.client.post(f"{API}/translate", json=body, headers=alice.headers)
    second = harness.client.post(f"{API}/translate", json=body, headers=alice.headers)

    assert first.status_code == 200
    assert second.status_code == 429 and "Retry-After" in second.headers
    assert len(provider(harness).calls) == 1


def test_provider_outage_leaves_chat_and_the_rest_of_the_app_working(harness: Harness) -> None:
    from app.integrations.ai.base import AiProviderError

    alice, _bob, conversation_id = chatting(harness)
    enable(harness, alice)
    outage = AiProviderError("unavailable", "down")
    provider(harness).queue(outage, outage)

    failed = harness.client.post(
        f"{API}/suggest-replies", json={"conversation_id": conversation_id}, headers=alice.headers
    )
    manual = send(harness, alice, conversation_id, "I can type this myself")

    assert failed.status_code == 502 and failed.json()["error"]["code"] == "ai_unavailable"
    assert manual.status_code in (200, 201)
    (row,) = harness.sql(
        "select outcome, error_code from public.ai_assistance_logs "
        "where user_id = $1 order by created_at desc limit 1",
        uuid.UUID(alice.id),
    )
    assert (row["outcome"], row["error_code"]) == ("unavailable", "unavailable")
