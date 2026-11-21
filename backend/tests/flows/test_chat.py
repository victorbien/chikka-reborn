"""Module C: real-time Chikka-to-Chikka messaging.

Two (or three) separately signed-in users talk through the real REST API, the real WebSocket
gateway and the real migrated database. Only Supabase Auth/Storage are faked.

WebSocket assertions never wait on a timer: `sync(ws)` sends a ping and returns every frame that
arrived before the pong. Events are queued in order, so anything published before the ping is
in that list, and "nothing arrived" is a definite answer rather than a timeout.
"""

import asyncio
import io
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import asyncpg
import pytest
from PIL import Image
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from tests.flows.conftest import Harness
from tests.flows.test_contacts import Person, befriend, make_person

API = "/api/v1"


# -- helpers ----------------------------------------------------------------------------------


def token_of(person: Person) -> str:
    return person.headers["Authorization"].removeprefix("Bearer ")


@contextmanager
def socket(harness: Harness, person: Person) -> Iterator[WebSocketTestSession]:
    with harness.client.websocket_connect("/ws/v1") as ws:
        ws.send_json({"type": "auth", "token": token_of(person)})
        ready = ws.receive_json()
        assert ready["type"] == "ready", ready
        assert ready["heartbeat_s"] == 25
        yield ws


def sync(ws: WebSocketTestSession) -> list[dict[str, Any]]:
    """Frames received before the reply to a ping (see module docstring)."""
    ws.send_json({"type": "ping"})
    frames: list[dict[str, Any]] = []
    while True:
        frame = ws.receive_json()
        if frame["type"] == "pong":
            return frames
        frames.append(frame)


def of_type(frames: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [f for f in frames if f["type"] == kind]


def open_conversation(harness: Harness, person: Person, other: Person) -> dict[str, Any]:
    response = harness.client.post(
        f"{API}/conversations", json={"user_id": other.id}, headers=person.headers
    )
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def send(
    harness: Harness,
    person: Person,
    conversation_id: str,
    body: str | None = "Hello",
    *,
    client_id: str | None = None,
    attachment_ids: list[str] | None = None,
) -> Any:
    payload: dict[str, Any] = {"client_message_id": client_id or str(uuid.uuid4())}
    if body is not None:
        payload["body"] = body
    if attachment_ids:
        payload["attachment_ids"] = attachment_ids
    return harness.client.post(
        f"{API}/conversations/{conversation_id}/messages", json=payload, headers=person.headers
    )


def history(harness: Harness, person: Person, conversation_id: str, **params: Any) -> Any:
    response = harness.client.get(
        f"{API}/conversations/{conversation_id}/messages", params=params, headers=person.headers
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def conversations(harness: Harness, person: Person, **params: Any) -> list[dict[str, Any]]:
    response = harness.client.get(f"{API}/conversations", params=params, headers=person.headers)
    assert response.status_code == 200, response.text
    return list(response.json()["data"])


def pair(harness: Harness) -> tuple[Person, Person, str]:
    alice, bob = make_person(harness, "Alice Reyes"), make_person(harness, "Bob Cruz")
    befriend(harness, alice, bob)
    return alice, bob, open_conversation(harness, alice, bob)["id"]


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 30, 30)).save(output, format="PNG")
    return output.getvalue()


def upload(harness: Harness, person: Person, conversation_id: str, data: bytes, name: str) -> Any:
    return harness.client.post(
        f"{API}/conversations/{conversation_id}/attachments",
        files={"file": (name, data, "application/octet-stream")},
        headers=person.headers,
    )


# -- the core requirement: two sessions exchange messages -------------------------------------


def test_two_signed_in_users_exchange_messages_in_real_time(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)

    with socket(harness, alice) as alice_ws, socket(harness, bob) as bob_ws:
        sent = send(harness, alice, conversation_id, "Kumusta, Bob?")
        assert sent.status_code == 201, sent.text
        message = sent.json()["data"]
        assert message["status"] == "sent"
        assert message["is_mine"] is True

        # Bob receives it live, as the REST API would show it to him.
        bob_frames = of_type(sync(bob_ws), "message.created")
        assert len(bob_frames) == 1
        received = bob_frames[0]["data"]["message"]
        assert received["id"] == message["id"]
        assert received["body"] == "Kumusta, Bob?"
        assert received["is_mine"] is False
        assert received["sender_user_id"] == alice.id
        assert received["status"] is None  # the sender's delivery state is not his business
        assert received["client_message_id"] is None
        assert bob_frames[0]["conversation_id"] == conversation_id

        # The push alone is not "delivered": Alice still sees "sent" until Bob's app acks.
        alice_frames = sync(alice_ws)
        assert of_type(alice_frames, "message.status_changed") == []
        assert of_type(alice_frames, "message.created")[0]["data"]["message"]["is_mine"] is True

        bob_ws.send_json({"type": "ack", "message_ids": [received["id"]]})
        sync(bob_ws)
        status = of_type(sync(alice_ws), "message.status_changed")
        assert [s["data"]["status"] for s in status] == ["delivered"]
        assert status[0]["data"]["message_id"] == message["id"]
        assert status[0]["data"]["delivered_at"] is not None

        reply = send(harness, bob, conversation_id, "Mabuti! Ikaw?")
        assert reply.status_code == 201
        live = of_type(sync(alice_ws), "message.created")
        assert [m["data"]["message"]["body"] for m in live] == ["Mabuti! Ikaw?"]

    # Both see the same ordered history.
    for person in (alice, bob):
        page = history(harness, person, conversation_id)
        assert [m["body"] for m in page["messages"]] == ["Kumusta, Bob?", "Mabuti! Ikaw?"]
        assert [m["seq"] for m in page["messages"]] == [1, 2]


def test_sender_info_timestamps_and_delivery_state_in_history(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    send(harness, alice, conversation_id, "First")
    mine = history(harness, alice, conversation_id)["messages"][0]
    assert mine["sender_user_id"] == alice.id
    assert mine["created_at"]
    assert mine["status"] == "sent"
    assert mine["client_message_id"]

    theirs = history(harness, bob, conversation_id)["messages"][0]
    assert theirs["sender_user_id"] == alice.id
    assert theirs["status"] is None

    # Bob loading the conversation means his app has the message: now it is delivered.
    again = history(harness, alice, conversation_id)["messages"][0]
    assert again["status"] == "delivered"
    assert again["status_version"] > mine["status_version"]


# -- duplicates and idempotency ---------------------------------------------------------------


def test_retrying_with_the_same_client_id_stores_and_pushes_once(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    client_id = str(uuid.uuid4())
    with socket(harness, bob) as bob_ws:
        first = send(harness, alice, conversation_id, "Only once", client_id=client_id)
        retry = send(harness, alice, conversation_id, "Only once", client_id=client_id)
        assert (first.status_code, retry.status_code) == (201, 200)
        assert retry.json()["data"]["id"] == first.json()["data"]["id"]
        assert len(of_type(sync(bob_ws), "message.created")) == 1

    rows = harness.sql(
        "select count(*) as n from public.messages where conversation_id = $1",
        uuid.UUID(conversation_id),
    )
    assert rows[0]["n"] == 1
    assert len(history(harness, bob, conversation_id)["messages"]) == 1


def test_reusing_a_client_id_for_different_content_is_rejected(harness: Harness) -> None:
    alice, _, conversation_id = pair(harness)
    client_id = str(uuid.uuid4())
    assert send(harness, alice, conversation_id, "One", client_id=client_id).status_code == 201
    clash = send(harness, alice, conversation_id, "Two", client_id=client_id)
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "idempotency_conflict"


def test_a_retry_does_not_count_against_the_rate_limit(harness: Harness) -> None:
    alice, _, conversation_id = pair(harness)
    client_id = str(uuid.uuid4())
    for _ in range(70):
        assert send(harness, alice, conversation_id, "Same", client_id=client_id).status_code in (
            200,
            201,
        )


def test_sending_is_rate_limited(harness: Harness) -> None:
    alice, _, conversation_id = pair(harness)
    codes = [send(harness, alice, conversation_id, f"n{i}").status_code for i in range(61)]
    assert codes[:60] == [201] * 60
    assert codes[60] == 429


# -- offline recipients and reconnection ------------------------------------------------------


def test_offline_recipient_gets_messages_later_and_sender_learns_of_delivery(
    harness: Harness,
) -> None:
    alice, bob, conversation_id = pair(harness)
    with socket(harness, alice) as alice_ws:
        # Bob has no connection at all.
        for text in ("Are you there?", "Call me"):
            assert send(harness, alice, conversation_id, text).status_code == 201
        sync(alice_ws)

        listed = conversations(harness, bob)
        assert listed[0]["unread_count"] == 2
        totals = harness.client.get(f"{API}/conversations/unread", headers=bob.headers).json()
        assert totals["data"] == {"unread_messages": 2, "unread_conversations": 1}

        # Bob comes online and loads the conversation: Alice is told both were delivered.
        page = history(harness, bob, conversation_id)
        assert [m["body"] for m in page["messages"]] == ["Are you there?", "Call me"]
        changes = of_type(sync(alice_ws), "message.status_changed")
        assert sorted(c["data"]["status"] for c in changes) == ["delivered", "delivered"]

    # Delivered is not read: the unread count stays until Bob marks them read.
    assert conversations(harness, bob)[0]["unread_count"] == 2
    read = harness.client.post(
        f"{API}/conversations/{conversation_id}/read",
        json={"up_to_seq": page["messages"][-1]["seq"]},
        headers=bob.headers,
    )
    assert read.status_code == 200
    assert read.json()["data"]["unread_count"] == 0
    assert conversations(harness, bob)[0]["unread_count"] == 0


def test_reconnecting_client_catches_up_without_gaps_or_duplicates(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    with socket(harness, bob) as bob_ws:
        send(harness, alice, conversation_id, "one")
        seen = [f["data"]["message"] for f in of_type(sync(bob_ws), "message.created")]
    last_seen = seen[-1]["seq"]

    # Bob's connection is gone (network drop). Two messages arrive meanwhile.
    send(harness, alice, conversation_id, "two")
    send(harness, alice, conversation_id, "three")

    with socket(harness, bob) as bob_ws:
        # A reconnect gets no replay over the socket: the REST sync is the replay.
        assert of_type(sync(bob_ws), "message.created") == []
        missed = history(harness, bob, conversation_id, after_seq=last_seen)["messages"]
        assert [(m["seq"], m["body"]) for m in missed] == [(2, "two"), (3, "three")]

        send(harness, alice, conversation_id, "four")
        live = [f["data"]["message"]["seq"] for f in of_type(sync(bob_ws), "message.created")]
        assert live == [4]


def test_history_pages_backwards_in_order(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    for i in range(5):
        send(harness, alice if i % 2 == 0 else bob, conversation_id, f"m{i}")
    latest = history(harness, alice, conversation_id, limit=2)
    assert [m["body"] for m in latest["messages"]] == ["m3", "m4"]
    assert latest["has_more_before"] is True
    older = history(
        harness, alice, conversation_id, limit=2, before_seq=latest["messages"][0]["seq"]
    )
    assert [m["body"] for m in older["messages"]] == ["m1", "m2"]
    oldest = history(
        harness, alice, conversation_id, limit=2, before_seq=older["messages"][0]["seq"]
    )
    assert [m["body"] for m in oldest["messages"]] == ["m0"]
    assert oldest["has_more_before"] is False
    both = harness.client.get(
        f"{API}/conversations/{conversation_id}/messages",
        params={"before_seq": 3, "after_seq": 1},
        headers=alice.headers,
    )
    assert both.status_code == 422


# -- membership and authorisation -------------------------------------------------------------


def test_outsiders_cannot_read_write_or_touch_a_conversation(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    message = send(harness, alice, conversation_id, "Private").json()["data"]
    mallory = make_person(harness, "Mallory")
    base = f"{API}/conversations/{conversation_id}"

    assert harness.client.get(base, headers=mallory.headers).status_code == 404
    assert harness.client.get(f"{base}/messages", headers=mallory.headers).status_code == 404
    assert send(harness, mallory, conversation_id, "Let me in").status_code == 404
    assert (
        harness.client.post(
            f"{base}/read", json={"up_to_seq": 1}, headers=mallory.headers
        ).status_code
        == 404
    )
    assert (
        harness.client.patch(base, json={"is_archived": True}, headers=mallory.headers).status_code
        == 404
    )
    assert upload(harness, mallory, conversation_id, png_bytes(), "x.png").status_code == 404
    assert conversations(harness, mallory) == []

    with socket(harness, mallory) as mallory_ws, socket(harness, bob) as bob_ws:
        # Faking a delivery ack or a typing event for someone else's conversation does nothing.
        mallory_ws.send_json({"type": "ack", "message_ids": [message["id"]]})
        mallory_ws.send_json({"type": "typing", "conversation_id": conversation_id})
        errors = of_type(sync(mallory_ws), "error")
        assert [e["code"] for e in errors] == ["forbidden"]
        assert sync(bob_ws) == []
    assert history(harness, alice, conversation_id)["messages"][0]["status"] == "sent"
    rows = harness.sql("select count(*) as n from public.messages where body = 'Let me in'")
    assert rows[0]["n"] == 0


def test_every_endpoint_requires_a_signed_in_user(harness: Harness) -> None:
    conversation_id = str(uuid.uuid4())
    for method, path in (
        ("get", "/conversations"),
        ("post", "/conversations"),
        ("get", "/conversations/unread"),
        ("get", f"/conversations/{conversation_id}"),
        ("get", f"/conversations/{conversation_id}/messages"),
        ("post", f"/conversations/{conversation_id}/messages"),
        ("post", f"/conversations/{conversation_id}/read"),
    ):
        assert getattr(harness.client, method)(f"{API}{path}").status_code == 401, path


def test_only_contacts_can_start_a_conversation(harness: Harness) -> None:
    alice, stranger = make_person(harness), make_person(harness)
    response = harness.client.post(
        f"{API}/conversations", json={"user_id": stranger.id}, headers=alice.headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_a_contact"
    unknown = harness.client.post(
        f"{API}/conversations", json={"user_id": str(uuid.uuid4())}, headers=alice.headers
    )
    assert unknown.status_code == 403
    assert unknown.json()["error"] == response.json()["error"]  # nothing to tell them apart
    own = harness.client.post(
        f"{API}/conversations", json={"user_id": alice.id}, headers=alice.headers
    )
    assert own.status_code == 422


def test_opening_twice_returns_the_same_single_conversation(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    assert open_conversation(harness, alice, bob)["id"] == conversation_id
    assert open_conversation(harness, bob, alice)["id"] == conversation_id


def test_messages_are_not_readable_through_the_database_by_outsiders(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    send(harness, alice, conversation_id, "Secret")
    mallory = make_person(harness)

    async def run(user_id: str, statement: str, *args: Any) -> list[Any]:
        connection = await asyncpg.connect(harness.database_url, statement_cache_size=0)
        try:
            async with connection.transaction():
                await connection.execute("set local role authenticated")
                await connection.execute(
                    "select set_config('request.jwt.claims', $1, true)", f'{{"sub":"{user_id}"}}'
                )
                return list(await connection.fetch(statement, *args))
        finally:
            await connection.close()

    assert asyncio.run(run(mallory.id, "select body from public.messages")) == []
    assert len(asyncio.run(run(bob.id, "select body from public.messages"))) == 1
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(
            run(
                bob.id,
                "insert into public.messages (conversation_id, channel, direction, sender_user_id,"
                " body, status, idempotency_key) values ($1, 'chikka', 'outbound', $2, 'x',"
                " 'sent', gen_random_uuid())",
                uuid.UUID(conversation_id),
                uuid.UUID(bob.id),
            )
        )


# -- blocking and contact changes -------------------------------------------------------------


def test_a_blocked_sender_sees_sent_but_the_recipient_never_receives(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    harness.client.post(f"{API}/contacts/blocks", json={"user_id": alice.id}, headers=bob.headers)

    with socket(harness, bob) as bob_ws:
        sent = send(harness, alice, conversation_id, "Hello?")
        assert sent.status_code == 201
        assert sent.json()["data"]["status"] == "sent"
        assert sync(bob_ws) == []

    assert [m["body"] for m in history(harness, alice, conversation_id)["messages"]] == ["Hello?"]
    # Bob blocked Alice, so the conversation leaves his list; nothing is waiting for him either.
    assert conversations(harness, bob) == []
    totals = harness.client.get(f"{API}/conversations/unread", headers=bob.headers).json()["data"]
    assert totals["unread_messages"] == 0

    # Bob cannot write to Alice while he blocks her, and is told why.
    blocked = send(harness, bob, conversation_id, "...")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "user_blocked"

    # After unblocking, the suppressed message is still not delivered retroactively.
    harness.client.delete(f"{API}/contacts/blocks/{alice.id}", headers=bob.headers)
    assert history(harness, bob, conversation_id)["messages"] == []


def test_former_contacts_cannot_keep_messaging(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    contact_id = next(
        c["id"]
        for c in harness.client.get(f"{API}/contacts", headers=alice.headers).json()["data"]
        if c["user_id"] == bob.id
    )
    harness.client.delete(f"{API}/contacts/{contact_id}", headers=alice.headers)
    response = send(harness, bob, conversation_id, "Still there?")
    assert response.status_code == 403
    summary = harness.client.get(
        f"{API}/conversations/{conversation_id}", headers=bob.headers
    ).json()["data"]
    assert summary["can_send"] is False
    assert summary["cannot_send_reason"]


# -- read receipts, unread counts, archive, search --------------------------------------------


def test_read_receipts_need_both_people_to_opt_in(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    first = send(harness, alice, conversation_id, "One").json()["data"]
    harness.client.post(
        f"{API}/conversations/{conversation_id}/read", json={"up_to_seq": 1}, headers=bob.headers
    )
    # Default is off: reading clears Bob's unread count but Alice only learns "delivered".
    assert history(harness, alice, conversation_id)["messages"][0]["status"] == "delivered"
    assert history(harness, alice, conversation_id)["peer_read_seq"] is None

    harness.sql(
        "update public.profiles set send_read_receipts = true where id = any($1::uuid[])",
        [uuid.UUID(alice.id), uuid.UUID(bob.id)],
    )
    with socket(harness, alice) as alice_ws:
        second = send(harness, alice, conversation_id, "Two").json()["data"]
        sync(alice_ws)
        harness.client.post(
            f"{API}/conversations/{conversation_id}/read",
            json={"up_to_seq": second["seq"]},
            headers=bob.headers,
        )
        changes = of_type(sync(alice_ws), "message.status_changed")
        assert {(c["data"]["message_id"], c["data"]["status"]) for c in changes} == {
            (first["id"], "read"),
            (second["id"], "read"),
        }
    page = history(harness, alice, conversation_id)
    assert [m["status"] for m in page["messages"]] == ["read", "read"]
    assert page["messages"][1]["read_at"] is not None
    assert page["peer_read_seq"] == second["seq"]


def test_read_position_never_moves_backwards_or_past_the_end(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    for text in ("a", "b", "c"):
        send(harness, alice, conversation_id, text)
    url = f"{API}/conversations/{conversation_id}/read"
    assert (
        harness.client.post(url, json={"up_to_seq": 99}, headers=bob.headers).json()["data"][
            "last_read_seq"
        ]
        == 3
    )
    assert (
        harness.client.post(url, json={"up_to_seq": 1}, headers=bob.headers).json()["data"][
            "last_read_seq"
        ]
        == 3
    )


def test_own_messages_never_count_as_unread(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    send(harness, alice, conversation_id, "mine")
    assert conversations(harness, alice)[0]["unread_count"] == 0
    assert conversations(harness, bob)[0]["unread_count"] == 1


def test_read_state_is_pushed_to_the_readers_other_devices(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    send(harness, alice, conversation_id, "hi")
    with socket(harness, bob) as phone, socket(harness, bob) as laptop:
        harness.client.post(
            f"{API}/conversations/{conversation_id}/read",
            json={"up_to_seq": 1},
            headers=bob.headers,
        )
        for ws in (phone, laptop):
            read = of_type(sync(ws), "conversation.read")
            assert read[0]["data"]["unread_count"] == 0


def test_archive_hides_until_a_new_message_arrives(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    send(harness, alice, conversation_id, "hi")
    archived = harness.client.patch(
        f"{API}/conversations/{conversation_id}", json={"is_archived": True}, headers=bob.headers
    )
    assert archived.json()["data"]["is_archived"] is True
    assert conversations(harness, bob) == []
    assert [c["id"] for c in conversations(harness, bob, archived=True)] == [conversation_id]
    # Archive is personal: Alice still sees it.
    assert [c["id"] for c in conversations(harness, alice)] == [conversation_id]

    send(harness, alice, conversation_id, "you there?")
    assert [c["id"] for c in conversations(harness, bob)] == [conversation_id]


def test_muted_conversations_stay_archived(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    send(harness, alice, conversation_id, "hi")
    harness.client.patch(
        f"{API}/conversations/{conversation_id}", json={"is_archived": True}, headers=bob.headers
    )
    harness.sql(
        "update public.conversation_members set muted_indefinitely = true"
        " where conversation_id = $1 and user_id = $2",
        uuid.UUID(conversation_id),
        uuid.UUID(bob.id),
    )
    send(harness, alice, conversation_id, "again")
    assert conversations(harness, bob) == []


def test_conversation_search_by_name_and_message_text(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    carol = make_person(harness, "Carol Dizon")
    befriend(harness, alice, carol)
    other = open_conversation(harness, alice, carol)["id"]
    send(harness, alice, conversation_id, "Let's meet at the palengke tomorrow")
    send(harness, alice, other, "Happy birthday!")

    def search(q: str) -> list[str]:
        return [c["id"] for c in conversations(harness, alice, q=q)]

    assert search("dizon") == [other]
    assert search("palengke") == [conversation_id]
    assert search("nothing-matches") == []
    assert (
        harness.client.get(
            f"{API}/conversations", params={"q": "a"}, headers=alice.headers
        ).status_code
        == 422
    )
    # Bob cannot find Alice's conversation with Carol by its content.
    assert [c["id"] for c in conversations(harness, bob, q="birthday")] == []


def test_conversation_list_shows_contact_last_message_and_order(harness: Harness) -> None:
    alice, _bob, conversation_id = pair(harness)
    carol = make_person(harness, "Carol Dizon")
    befriend(harness, alice, carol)
    other = open_conversation(harness, alice, carol)["id"]
    send(harness, alice, conversation_id, "older")
    send(harness, carol, other, "newer")
    listed = conversations(harness, alice)
    assert [c["id"] for c in listed] == [other, conversation_id]
    assert listed[0]["participant"]["display_name"] == "Carol Dizon"
    assert listed[0]["last_message"]["preview"] == "newer"
    assert listed[0]["last_message"]["is_mine"] is False
    assert listed[1]["last_message"]["status"] == "sent"
    assert listed[0]["can_send"] is True


# -- content: emoji, length, attachments ------------------------------------------------------


def test_emoji_round_trip_and_length_counts_code_points(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    text = "Ingat! 👋🏽🇵🇭 ❤️"
    send(harness, alice, conversation_id, text)
    assert history(harness, bob, conversation_id)["messages"][0]["body"] == text

    assert send(harness, alice, conversation_id, "😀" * 2000).status_code == 201
    too_long = send(harness, alice, conversation_id, "😀" * 2001)
    assert too_long.status_code == 422


def test_blank_messages_are_rejected_and_markup_is_kept_as_text(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    assert send(harness, alice, conversation_id, "   \n ").status_code == 422
    assert send(harness, alice, conversation_id, None).status_code == 422
    # Stored exactly as typed; the app renders it as text, never as HTML.
    send(harness, alice, conversation_id, "<b>not bold</b> <3")
    assert history(harness, bob, conversation_id)["messages"][0]["body"] == "<b>not bold</b> <3"


def test_attachments_are_validated_shared_and_private(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    uploaded = upload(harness, alice, conversation_id, png_bytes(), "../../etc/photo.png")
    assert uploaded.status_code == 201, uploaded.text
    attachment = uploaded.json()["data"]
    assert attachment["content_type"] == "image/png"
    assert attachment["file_name"] == "photo.png"
    assert attachment["url"]

    with socket(harness, bob) as bob_ws:
        # A photo with no text is a valid message.
        sent = send(harness, alice, conversation_id, None, attachment_ids=[attachment["id"]])
        assert sent.status_code == 201, sent.text
        pushed = of_type(sync(bob_ws), "message.created")[0]["data"]["message"]
        assert [a["id"] for a in pushed["attachments"]] == [attachment["id"]]
        assert pushed["attachments"][0]["url"]

    seen = history(harness, bob, conversation_id)["messages"][0]
    assert seen["body"] is None
    assert seen["attachments"][0]["file_name"] == "photo.png"
    preview = conversations(harness, bob)[0]["last_message"]
    assert preview["has_attachments"] is True

    # The same upload cannot be sent twice, and nobody else can send it.
    again = send(harness, alice, conversation_id, "again", attachment_ids=[attachment["id"]])
    assert again.status_code == 422
    other_upload = upload(harness, alice, conversation_id, png_bytes(), "b.png").json()["data"]
    stolen = send(harness, bob, conversation_id, "mine now", attachment_ids=[other_upload["id"]])
    assert stolen.status_code == 422
    assert stolen.json()["error"]["code"] == "attachment_unavailable"

    # The bucket path is never exposed to clients.
    assert "storage_path" not in seen["attachments"][0]


def test_attachment_type_is_checked_from_the_content(harness: Harness) -> None:
    alice, _, conversation_id = pair(harness)
    fake_image = upload(harness, alice, conversation_id, b"MZ\x90\x00 not an image", "cat.png")
    assert fake_image.status_code == 422
    assert fake_image.json()["error"]["code"] == "invalid_attachment"
    broken_png = upload(harness, alice, conversation_id, b"\x89PNG\r\n\x1a\nbroken", "a.png")
    assert broken_png.status_code == 422
    pdf = upload(harness, alice, conversation_id, b"%PDF-1.7\n%test\n", "notes.pdf")
    assert pdf.status_code == 201
    assert pdf.json()["data"]["content_type"] == "application/pdf"
    too_big = upload(harness, alice, conversation_id, b"%PDF-" + b"0" * (10 * 1024 * 1024), "x.pdf")
    assert too_big.status_code == 422
    six = [
        upload(harness, alice, conversation_id, png_bytes(), f"{i}.png").json()["data"]["id"]
        for i in range(6)
    ]
    assert send(harness, alice, conversation_id, "many", attachment_ids=six).status_code == 422


def test_image_metadata_is_removed(harness: Harness) -> None:
    alice, _, conversation_id = pair(harness)
    exif = Image.Exif()
    exif[0x010F] = "Camera Maker"  # Make
    output = io.BytesIO()
    Image.new("RGB", (8, 8)).save(output, format="JPEG", exif=exif)
    assert b"Camera Maker" in output.getvalue()
    response = upload(harness, alice, conversation_id, output.getvalue(), "pic.jpg")
    assert response.status_code == 201
    stored = next(
        data
        for key, (data, _) in harness.fake.objects.items()
        if key.startswith("message-attachments/")
    )
    assert b"Camera Maker" not in stored


# -- the WebSocket gateway itself -------------------------------------------------------------


def test_socket_requires_a_valid_token_in_the_first_frame(harness: Harness) -> None:
    with harness.client.websocket_connect("/ws/v1") as ws:
        ws.send_json({"type": "auth", "token": "not-a-token"})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401

    with harness.client.websocket_connect("/ws/v1") as ws:
        ws.send_json({"type": "ping"})  # anything but auth first is refused
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


def test_socket_closes_when_no_auth_frame_arrives(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import websocket as gateway

    monkeypatch.setattr(gateway, "AUTH_TIMEOUT_SECONDS", 0.2)
    with (
        harness.client.websocket_connect("/ws/v1") as ws,
        pytest.raises(WebSocketDisconnect) as closed,
    ):
        ws.receive_json()
    assert closed.value.code == 4408


def test_socket_refuses_foreign_origins(harness: Harness) -> None:
    with (
        pytest.raises(WebSocketDisconnect),
        harness.client.websocket_connect("/ws/v1", headers={"Origin": "https://evil.example"}),
    ):
        pass


def test_accounts_that_are_not_set_up_cannot_connect(harness: Harness) -> None:
    _, headers = harness.signed_up_user()  # verified but no username yet
    with harness.client.websocket_connect("/ws/v1") as ws:
        ws.send_json({"type": "auth", "token": headers["Authorization"].removeprefix("Bearer ")})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4403


def test_signing_out_closes_the_live_socket(harness: Harness) -> None:
    alice = make_person(harness)
    with socket(harness, alice) as ws:
        assert harness.client.post(f"{API}/auth/logout", headers=alice.headers).status_code == 204
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


def test_token_refresh_keeps_the_socket_open_for_the_same_user_only(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    with socket(harness, alice) as ws:
        ws.send_json({"type": "auth.refresh", "token": token_of(alice)})
        assert ws.receive_json()["type"] == "auth.ok"
        ws.send_json({"type": "auth.refresh", "token": token_of(bob)})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


def test_malformed_and_oversized_frames(harness: Harness) -> None:
    alice = make_person(harness)
    with socket(harness, alice) as ws:
        ws.send_json({"type": "launch_missiles"})
        assert [e["code"] for e in of_type(sync(ws), "error")] == ["invalid_frame"]
        ws.send_text("x" * (9 * 1024))
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 1009


def test_typing_reaches_the_other_person_only_if_they_share_it(harness: Harness) -> None:
    alice, bob, conversation_id = pair(harness)
    with socket(harness, alice) as alice_ws, socket(harness, bob) as bob_ws:
        alice_ws.send_json({"type": "typing", "conversation_id": conversation_id})
        sync(alice_ws)
        typing = of_type(sync(bob_ws), "typing")
        assert [t["data"]["user_id"] for t in typing] == [alice.id]
        # Throttled: a burst of keystrokes is one event per two seconds.
        alice_ws.send_json({"type": "typing", "conversation_id": conversation_id})
        sync(alice_ws)
        assert of_type(sync(bob_ws), "typing") == []

    harness.sql(
        "update public.profiles set send_typing_indicators = false where id = $1",
        uuid.UUID(bob.id),
    )
    with socket(harness, alice) as alice_ws, socket(harness, bob) as bob_ws:
        bob_ws.send_json({"type": "typing", "conversation_id": conversation_id})
        sync(bob_ws)
        assert of_type(sync(alice_ws), "typing") == []


def test_too_many_connections_replace_the_oldest(harness: Harness) -> None:
    alice = make_person(harness)
    with socket(harness, alice) as oldest:
        sockets = [socket(harness, alice) for _ in range(5)]
        opened = [s.__enter__() for s in sockets]
        try:
            with pytest.raises(WebSocketDisconnect) as closed:
                oldest.receive_json()
            assert closed.value.code == 4409
            assert all(sync(ws) == [] for ws in opened)
        finally:
            for s in reversed(sockets):
                s.__exit__(None, None, None)
