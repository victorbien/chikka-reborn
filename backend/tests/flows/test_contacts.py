"""Module B: contacts, requests, groups, blocks, presence and discovery.

These run against the real migrated database and the real auth dependency chain. Only the
external Supabase Auth/Storage services are faked. Names, emails and numbers are fabricated.
"""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg
import pytest

from tests.flows.conftest import Harness

API = "/api/v1"
FAKE_PHONE = "+639171234567"  # A valid-format number; never contacted.


@dataclass
class Person:
    email: str
    headers: dict[str, str]
    id: str
    username: str


def make_person(harness: Harness, name: str = "Test Person") -> Person:
    email, headers = harness.signed_up_user()
    username = f"u_{uuid.uuid4().hex[:10]}"
    response = harness.client.post(
        f"{API}/users/me/onboarding",
        json={"username": username, "display_name": name},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return Person(email, headers, response.json()["data"]["id"], username)


def request_contact(
    harness: Harness, sender: Person, target: Person, note: str | None = None
) -> Any:
    return harness.client.post(
        f"{API}/contacts/requests",
        json={"user_id": target.id, "note": note},
        headers=sender.headers,
    )


def incoming(harness: Harness, person: Person) -> list[dict[str, Any]]:
    response = harness.client.get(f"{API}/contacts/requests", headers=person.headers)
    assert response.status_code == 200, response.text
    return list(response.json()["data"])


def befriend(harness: Harness, first: Person, second: Person) -> tuple[str, str]:
    """Make two people mutual contacts. Returns (first's contact id, second's contact id)."""
    assert request_contact(harness, first, second).status_code == 200
    pending = incoming(harness, second)
    assert len(pending) == 1
    accepted = harness.client.post(
        f"{API}/contacts/requests/{pending[0]['id']}/accept", headers=second.headers
    )
    assert accepted.status_code == 200, accepted.text
    second_contact = accepted.json()["data"]["id"]
    return contact_id_of(harness, first, second), second_contact


def contact_id_of(harness: Harness, owner: Person, other: Person) -> str:
    rows = harness.client.get(f"{API}/contacts", headers=owner.headers).json()["data"]
    return next(row["id"] for row in rows if row["user_id"] == other.id)


def contacts(harness: Harness, person: Person, **params: Any) -> list[dict[str, Any]]:
    response = harness.client.get(f"{API}/contacts", params=params, headers=person.headers)
    assert response.status_code == 200, response.text
    return list(response.json()["data"])


def search(harness: Harness, person: Person, query: str) -> Any:
    return harness.client.get(f"{API}/contacts/search", params={"q": query}, headers=person.headers)


def set_privacy(harness: Harness, person: Person, **changes: Any) -> None:
    response = harness.client.patch(f"{API}/users/me/privacy", json=changes, headers=person.headers)
    assert response.status_code == 200, response.text


def beat(harness: Harness, person: Person) -> None:
    response = harness.client.post(
        f"{API}/users/me/presence/heartbeat", json={"idle": False}, headers=person.headers
    )
    assert response.status_code == 200


# -- access control ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/contacts"),
        ("get", "/contacts/search?q=abc"),
        ("get", "/contacts/requests"),
        ("post", "/contacts/requests"),
        ("get", "/contacts/groups"),
        ("get", "/contacts/blocks"),
        ("get", "/contacts/recent"),
        ("get", "/contacts/recent-conversations"),
        ("get", f"/contacts/{uuid.uuid4()}"),
    ],
)
def test_every_contacts_endpoint_requires_authentication(
    harness: Harness, method: str, path: str
) -> None:
    response = getattr(harness.client, method)(f"{API}{path}")
    assert response.status_code == 401


def test_unverified_account_cannot_use_contacts(harness: Harness) -> None:
    email = harness.email()
    assert harness.register(email).status_code == 202
    # Sign-in is refused until verified, so no usable token exists for this account.
    assert harness.login(email).status_code in (401, 403)


# -- discovery and privacy --------------------------------------------------------------------


def test_exact_username_finds_a_person_with_a_minimal_card(harness: Harness) -> None:
    alice, bob = make_person(harness, "Alice Reyes"), make_person(harness, "Bob Cruz")
    response = search(harness, alice, bob.username.upper())  # Case-insensitive, exact.
    assert response.status_code == 200
    people = response.json()["data"]["people"]
    assert len(people) == 1
    assert set(people[0]) == {
        "user_id",
        "username",
        "display_name",
        "avatar_url",
        "relationship",
        "contact_id",
        "request_id",
    }
    assert people[0]["user_id"] == bob.id
    assert people[0]["relationship"] == "none"


def test_username_search_is_exact_not_a_directory(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    assert search(harness, alice, bob.username[:-2]).json()["data"]["people"] == []


def test_search_never_returns_yourself(harness: Harness) -> None:
    alice = make_person(harness)
    assert search(harness, alice, alice.username).json()["data"]["people"] == []


def test_private_profiles_are_never_discoverable(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    set_privacy(harness, bob, profile_visibility="private", discoverable_by_email=True)
    assert search(harness, alice, bob.username).json()["data"]["people"] == []
    assert search(harness, alice, bob.email).json()["data"]["people"] == []


def test_email_search_requires_opt_in_and_does_not_reveal_registration(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    registered_but_hidden = search(harness, alice, bob.email).json()
    never_registered = search(harness, alice, f"nobody-{uuid.uuid4().hex[:8]}@example.com").json()
    # The two responses carry the same data, so the caller cannot tell them apart.
    assert (
        registered_but_hidden["data"]
        == never_registered["data"]
        == {
            "contacts": [],
            "people": [],
        }
    )

    set_privacy(harness, bob, discoverable_by_email=True)
    found = search(harness, alice, bob.email.upper()).json()["data"]["people"]
    assert [p["user_id"] for p in found] == [bob.id]

    set_privacy(harness, bob, discoverable_by_email=False)
    assert search(harness, alice, bob.email).json()["data"]["people"] == []


def _verify_phone(harness: Harness, person: Person, e164: str) -> None:
    harness.sql(
        "insert into public.phone_numbers (user_id, e164, country_code, verification_mode,"
        " status, verified_at) values ($1, $2, 'PH', 'simulated', 'verified', now())",
        uuid.UUID(person.id),
        e164,
    )


def test_phone_search_requires_opt_in_and_does_not_reveal_registration(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    _verify_phone(harness, bob, FAKE_PHONE)

    hidden = search(harness, alice, FAKE_PHONE).json()["data"]
    unknown = search(harness, alice, "+639170000001").json()["data"]
    assert hidden == unknown == {"contacts": [], "people": []}

    set_privacy(harness, bob, discoverable_by_phone=True)
    found = search(harness, alice, "+63 917 123 4567").json()["data"]["people"]
    assert [p["user_id"] for p in found] == [bob.id]
    # The number itself is never echoed back.
    assert FAKE_PHONE not in search(harness, alice, FAKE_PHONE).text


def test_search_requires_two_characters(harness: Harness) -> None:
    alice = make_person(harness)
    response = search(harness, alice, "a")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "query_too_short"


def test_search_is_rate_limited(harness: Harness) -> None:
    alice = make_person(harness)
    statuses = [search(harness, alice, "zz_nobody").status_code for _ in range(21)]
    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


def test_search_looks_through_own_contacts_by_name(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness, "Roberto Dimagiba")
    befriend(harness, alice, bob)
    found = search(harness, alice, "dimag").json()["data"]
    assert [c["user_id"] for c in found["contacts"]] == [bob.id]
    # A wildcard character is a literal, not a pattern.
    assert search(harness, alice, "%%").json()["data"]["contacts"] == []


def test_blocked_people_are_excluded_from_search_in_both_directions(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    assert (
        harness.client.post(
            f"{API}/contacts/blocks", json={"user_id": bob.id}, headers=alice.headers
        ).status_code
        == 201
    )
    assert search(harness, alice, bob.username).json()["data"]["people"] == []
    assert search(harness, bob, alice.username).json()["data"]["people"] == []


# -- requests ---------------------------------------------------------------------------------


def test_request_accept_creates_two_linked_contacts(harness: Harness) -> None:
    alice, bob = make_person(harness, "Alice Reyes"), make_person(harness, "Bob Cruz")
    assert request_contact(harness, alice, bob, "Hi, it's Alice").json()["data"] == {
        "status": "sent"
    }

    pending = incoming(harness, bob)
    assert len(pending) == 1
    assert pending[0]["person"]["user_id"] == alice.id
    assert pending[0]["note"] == "Hi, it's Alice"
    sent = harness.client.get(
        f"{API}/contacts/requests", params={"direction": "outgoing"}, headers=alice.headers
    ).json()["data"]
    assert [r["person"]["user_id"] for r in sent] == [bob.id]
    # Nobody is a contact until the request is accepted.
    assert contacts(harness, alice) == contacts(harness, bob) == []

    accepted = harness.client.post(
        f"{API}/contacts/requests/{pending[0]['id']}/accept", headers=bob.headers
    )
    assert accepted.status_code == 200
    assert accepted.json()["data"]["user_id"] == alice.id
    assert [c["user_id"] for c in contacts(harness, alice)] == [bob.id]
    assert [c["user_id"] for c in contacts(harness, bob)] == [alice.id]
    rows = harness.sql(
        "select count(*) as n from public.contacts where owner_id = any($1::uuid[])",
        [uuid.UUID(alice.id), uuid.UUID(bob.id)],
    )
    assert rows[0]["n"] == 2
    assert incoming(harness, bob) == []

    # Accepting again is harmless and creates nothing new.
    again = harness.client.post(
        f"{API}/contacts/requests/{pending[0]['id']}/accept", headers=bob.headers
    )
    assert again.status_code == 200
    assert len(contacts(harness, bob)) == 1


def test_duplicate_requests_create_one_row(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    for _ in range(3):
        assert request_contact(harness, alice, bob).status_code == 200
    rows = harness.sql(
        "select count(*) as n from public.contact_requests where from_user_id = $1",
        uuid.UUID(alice.id),
    )
    assert rows[0]["n"] == 1


def test_request_note_is_sanitised_and_limited(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    assert request_contact(harness, alice, bob, "x" * 141).status_code == 422
    assert (
        request_contact(harness, alice, bob, "Hi <script>alert(1)</script>there").status_code == 200
    )
    note = incoming(harness, bob)[0]["note"]
    assert "<script>" not in note


def test_cannot_request_yourself(harness: Harness) -> None:
    alice = make_person(harness)
    assert request_contact(harness, alice, alice).status_code == 422


def test_request_to_unknown_user_looks_like_success(harness: Harness) -> None:
    alice = make_person(harness)
    ghost = Person("", {}, str(uuid.uuid4()), "ghost")
    ghost.headers = alice.headers
    response = request_contact(harness, alice, ghost)
    assert response.status_code == 200
    assert response.json()["data"] == {"status": "sent"}


def test_request_to_private_profile_is_silently_dropped(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    set_privacy(harness, bob, profile_visibility="private")
    assert request_contact(harness, alice, bob).json()["data"] == {"status": "sent"}
    assert incoming(harness, bob) == []


def test_reverse_request_connects_both_immediately(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    request_contact(harness, alice, bob)
    response = request_contact(harness, bob, alice)
    assert response.json()["data"] == {"status": "contacts"}
    assert [c["user_id"] for c in contacts(harness, alice)] == [bob.id]
    assert [c["user_id"] for c in contacts(harness, bob)] == [alice.id]


def test_requesting_an_existing_contact_is_a_no_op(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    befriend(harness, alice, bob)
    assert request_contact(harness, alice, bob).json()["data"] == {"status": "contacts"}


def test_only_the_recipient_can_accept_or_reject(harness: Harness) -> None:
    alice, bob, mallory = make_person(harness), make_person(harness), make_person(harness)
    request_contact(harness, alice, bob)
    request_id = incoming(harness, bob)[0]["id"]
    for actor in (alice, mallory):
        for action in ("accept", "reject"):
            response = harness.client.post(
                f"{API}/contacts/requests/{request_id}/{action}", headers=actor.headers
            )
            assert response.status_code == 404, (actor.username, action)
    assert contacts(harness, alice) == []


def test_only_the_sender_can_cancel(harness: Harness) -> None:
    alice, bob, mallory = make_person(harness), make_person(harness), make_person(harness)
    request_contact(harness, alice, bob)
    request_id = incoming(harness, bob)[0]["id"]
    for actor in (bob, mallory):
        response = harness.client.delete(
            f"{API}/contacts/requests/{request_id}", headers=actor.headers
        )
        assert response.status_code == 404
    assert (
        harness.client.delete(
            f"{API}/contacts/requests/{request_id}", headers=alice.headers
        ).status_code
        == 204
    )
    assert incoming(harness, bob) == []


def test_reject_is_silent_and_resend_waits_seven_days(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    request_contact(harness, alice, bob)
    request_id = incoming(harness, bob)[0]["id"]
    assert (
        harness.client.post(
            f"{API}/contacts/requests/{request_id}/reject", headers=bob.headers
        ).status_code
        == 204
    )

    # The sender sees no trace of the rejection.
    outgoing = harness.client.get(
        f"{API}/contacts/requests", params={"direction": "outgoing"}, headers=alice.headers
    ).json()["data"]
    assert outgoing == []
    # A new request inside the cooling-off window looks successful but creates nothing.
    assert request_contact(harness, alice, bob).json()["data"] == {"status": "sent"}
    assert incoming(harness, bob) == []

    harness.sql(
        "update public.contact_requests set responded_at = now() - interval '8 days' where id = $1",
        uuid.UUID(request_id),
    )
    assert request_contact(harness, alice, bob).status_code == 200
    assert len(incoming(harness, bob)) == 1


def test_reject_and_block_removes_the_sender_from_view(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    request_contact(harness, alice, bob)
    request_id = incoming(harness, bob)[0]["id"]
    response = harness.client.post(
        f"{API}/contacts/requests/{request_id}/reject", json={"block": True}, headers=bob.headers
    )
    assert response.status_code == 204
    blocks = harness.client.get(f"{API}/contacts/blocks", headers=bob.headers).json()["data"]
    assert [b["user_id"] for b in blocks] == [alice.id]


def test_expired_requests_disappear_and_cannot_be_accepted(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    request_contact(harness, alice, bob)
    request_id = incoming(harness, bob)[0]["id"]
    harness.sql(
        "update public.contact_requests set expires_at = now() - interval '1 minute' where id = $1",
        uuid.UUID(request_id),
    )
    assert incoming(harness, bob) == []
    response = harness.client.post(
        f"{API}/contacts/requests/{request_id}/accept", headers=bob.headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "request_unavailable"
    # The stale pending row does not stop a fresh request.
    assert request_contact(harness, alice, bob).status_code == 200
    assert len(incoming(harness, bob)) == 1


def test_request_daily_limit(harness: Harness) -> None:
    alice = make_person(harness)
    codes = [
        harness.client.post(
            f"{API}/contacts/requests", json={"user_id": str(uuid.uuid4())}, headers=alice.headers
        ).status_code
        for _ in range(31)
    ]
    assert codes[:30] == [200] * 30
    assert codes[30] == 429


def test_accept_into_a_group(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    group = harness.client.post(
        f"{API}/contacts/groups", json={"name": "Family"}, headers=bob.headers
    ).json()["data"]
    request_contact(harness, alice, bob)
    request_id = incoming(harness, bob)[0]["id"]
    accepted = harness.client.post(
        f"{API}/contacts/requests/{request_id}/accept",
        json={"group_id": group["id"]},
        headers=bob.headers,
    )
    assert accepted.json()["data"]["group_ids"] == [group["id"]]


def test_accept_with_someone_elses_group_fails(harness: Harness) -> None:
    alice, bob, mallory = make_person(harness), make_person(harness), make_person(harness)
    foreign = harness.client.post(
        f"{API}/contacts/groups", json={"name": "Mine"}, headers=mallory.headers
    ).json()["data"]
    request_contact(harness, alice, bob)
    request_id = incoming(harness, bob)[0]["id"]
    response = harness.client.post(
        f"{API}/contacts/requests/{request_id}/accept",
        json={"group_id": foreign["id"]},
        headers=bob.headers,
    )
    assert response.status_code == 404
    assert contacts(harness, bob) == []


# -- blocking ---------------------------------------------------------------------------------


def test_blocked_sender_gets_no_signal_and_nothing_is_created(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    assert (
        harness.client.post(
            f"{API}/contacts/blocks", json={"user_id": alice.id}, headers=bob.headers
        ).status_code
        == 201
    )
    blocked = request_contact(harness, alice, bob)
    unblocked = request_contact(harness, alice, make_person(harness))
    assert blocked.status_code == unblocked.status_code == 200
    assert blocked.json()["data"] == unblocked.json()["data"]
    assert incoming(harness, bob) == []


def test_blocker_must_unblock_before_requesting(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    harness.client.post(f"{API}/contacts/blocks", json={"user_id": bob.id}, headers=alice.headers)
    response = request_contact(harness, alice, bob)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_blocked"


def test_blocking_hides_the_contact_and_unblocking_restores_it(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    befriend(harness, alice, bob)
    beat(harness, bob)

    blocked = harness.client.post(
        f"{API}/contacts/blocks", json={"user_id": bob.id}, headers=alice.headers
    )
    assert blocked.status_code == 201
    assert blocked.json()["data"]["person"]["user_id"] == bob.id
    # Hidden for both sides: the blocked person also loses sight of the blocker.
    assert contacts(harness, alice) == []
    assert contacts(harness, bob) == []

    assert (
        harness.client.delete(f"{API}/contacts/blocks/{bob.id}", headers=alice.headers).status_code
        == 204
    )
    assert [c["user_id"] for c in contacts(harness, alice)] == [bob.id]
    assert [c["user_id"] for c in contacts(harness, bob)] == [alice.id]


def test_blocking_withdraws_pending_requests(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    request_contact(harness, alice, bob)
    harness.client.post(f"{API}/contacts/blocks", json={"user_id": alice.id}, headers=bob.headers)
    assert incoming(harness, bob) == []
    rows = harness.sql(
        "select status from public.contact_requests where from_user_id = $1", uuid.UUID(alice.id)
    )
    assert [r["status"] for r in rows] == ["cancelled"]


def test_unblocking_does_not_re_add_a_removed_contact(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    alice_contact, _ = befriend(harness, alice, bob)
    harness.client.post(f"{API}/contacts/blocks", json={"user_id": bob.id}, headers=alice.headers)
    assert (
        harness.client.delete(f"{API}/contacts/{alice_contact}", headers=alice.headers).status_code
        == 204
    )
    harness.client.delete(f"{API}/contacts/blocks/{bob.id}", headers=alice.headers)
    assert contacts(harness, alice) == []


def test_block_validation(harness: Harness) -> None:
    alice = make_person(harness)
    own = harness.client.post(
        f"{API}/contacts/blocks", json={"user_id": alice.id}, headers=alice.headers
    )
    assert own.status_code == 422
    missing = harness.client.post(
        f"{API}/contacts/blocks", json={"user_id": str(uuid.uuid4())}, headers=alice.headers
    )
    assert missing.status_code == 404


def test_blocking_twice_is_harmless_and_block_list_is_private(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    for _ in range(2):
        assert (
            harness.client.post(
                f"{API}/contacts/blocks", json={"user_id": bob.id}, headers=alice.headers
            ).status_code
            == 201
        )
    assert (
        len(harness.client.get(f"{API}/contacts/blocks", headers=alice.headers).json()["data"]) == 1
    )
    # The blocked person cannot see that they were blocked.
    assert harness.client.get(f"{API}/contacts/blocks", headers=bob.headers).json()["data"] == []


# -- buddy list -------------------------------------------------------------------------------


def test_buddy_list_orders_favourites_first_then_alphabetical(harness: Harness) -> None:
    owner = make_person(harness)
    zed, amy, mia = (make_person(harness, n) for n in ("Zed Zamora", "Amy Abad", "Mia Mercado"))
    ids = {p.id: befriend(harness, owner, p)[0] for p in (zed, amy, mia)}
    assert [c["display_name"] for c in contacts(harness, owner)] == [
        "Amy Abad",
        "Mia Mercado",
        "Zed Zamora",
    ]
    star = harness.client.patch(
        f"{API}/contacts/{ids[zed.id]}", json={"is_favourite": True}, headers=owner.headers
    )
    assert star.status_code == 200
    assert star.json()["data"]["is_favourite"] is True
    assert next(c["display_name"] for c in contacts(harness, owner)) == "Zed Zamora"
    assert [c["display_name"] for c in contacts(harness, owner, filter="favourites")] == [
        "Zed Zamora"
    ]


def test_favourite_flag_is_private_to_the_owner(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    alice_contact, _ = befriend(harness, alice, bob)
    harness.client.patch(
        f"{API}/contacts/{alice_contact}", json={"is_favourite": True}, headers=alice.headers
    )
    assert contacts(harness, bob)[0]["is_favourite"] is False


def test_nickname_overrides_display_name_and_can_be_cleared(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness, "Roberto Cruz")
    alice_contact, _ = befriend(harness, alice, bob)
    named = harness.client.patch(
        f"{API}/contacts/{alice_contact}", json={"nickname": "Bert"}, headers=alice.headers
    ).json()["data"]
    assert (named["display_name"], named["nickname"]) == ("Bert", "Bert")
    cleared = harness.client.patch(
        f"{API}/contacts/{alice_contact}", json={"nickname": None}, headers=alice.headers
    ).json()["data"]
    assert (cleared["display_name"], cleared["nickname"]) == ("Roberto Cruz", None)
    assert (
        harness.client.patch(
            f"{API}/contacts/{alice_contact}", json={"is_favourite": None}, headers=alice.headers
        ).status_code
        == 422
    )


def test_online_and_offline_filters_follow_presence(harness: Harness) -> None:
    owner = make_person(harness)
    online, offline = make_person(harness, "On Line"), make_person(harness, "Off Line")
    befriend(harness, owner, online)
    befriend(harness, owner, offline)
    beat(harness, online)

    assert [c["user_id"] for c in contacts(harness, owner, filter="online")] == [online.id]
    assert [c["user_id"] for c in contacts(harness, owner, filter="offline")] == [offline.id]
    assert {c["user_id"] for c in contacts(harness, owner)} == {online.id, offline.id}
    assert (
        next(c for c in contacts(harness, owner) if c["user_id"] == online.id)["presence"]
        == "online"
    )


def test_invisible_contacts_appear_offline(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    befriend(harness, alice, bob)
    beat(harness, bob)
    harness.client.put(
        f"{API}/users/me/presence", json={"preference": "invisible"}, headers=bob.headers
    )
    assert contacts(harness, alice)[0]["presence"] == "offline"


def test_presence_can_be_hidden_and_is_then_unknown_not_offline(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    befriend(harness, alice, bob)
    beat(harness, bob)
    set_privacy(harness, bob, share_presence="nobody", show_last_seen=True)
    entry = contacts(harness, alice)[0]
    assert entry["presence"] == "unknown"
    assert entry["last_seen_at"] is None


def test_last_seen_is_shown_only_when_the_contact_allows_it(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    befriend(harness, alice, bob)
    beat(harness, bob)
    assert contacts(harness, alice)[0]["last_seen_at"] is None
    set_privacy(harness, bob, show_last_seen=True)
    assert contacts(harness, alice)[0]["last_seen_at"] is not None


def test_status_message_is_shown_to_contacts_but_hidden_for_private_profiles(
    harness: Harness,
) -> None:
    alice, bob = make_person(harness), make_person(harness)
    befriend(harness, alice, bob)
    updated = harness.client.patch(
        f"{API}/users/me", json={"status_message": "  At <b>work</b>  "}, headers=bob.headers
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status_message"] == "At work"
    entry = contacts(harness, alice)[0]
    assert entry["status_message"] == "At work"

    set_privacy(harness, bob, profile_visibility="private")
    hidden = contacts(harness, alice)[0]
    assert hidden["status_message"] is None
    assert hidden["display_name"]  # The relationship still identifies them.
    detail = harness.client.get(f"{API}/contacts/{hidden['id']}", headers=alice.headers).json()[
        "data"
    ]
    assert detail["bio"] is None


def test_status_message_length_limit(harness: Harness) -> None:
    alice = make_person(harness)
    too_long = harness.client.patch(
        f"{API}/users/me", json={"status_message": "x" * 81}, headers=alice.headers
    )
    assert too_long.status_code == 422


def test_contact_profile_includes_details(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness, "Bob Cruz")
    harness.client.patch(f"{API}/users/me", json={"bio": "Hello there"}, headers=bob.headers)
    alice_contact, _ = befriend(harness, alice, bob)
    detail = harness.client.get(f"{API}/contacts/{alice_contact}", headers=alice.headers).json()[
        "data"
    ]
    assert detail["bio"] == "Hello there"
    assert detail["username"] == bob.username
    assert detail["added_at"]
    assert "email" not in detail


def test_list_is_paginated(harness: Harness) -> None:
    owner = make_person(harness)
    for index in range(3):
        befriend(harness, owner, make_person(harness, f"Friend {index:02d}"))
    response = harness.client.get(
        f"{API}/contacts", params={"page": 2, "page_size": 2}, headers=owner.headers
    ).json()
    assert [c["display_name"] for c in response["data"]] == ["Friend 02"]
    assert response["pagination"] == {
        "total": 3,
        "page": 2,
        "page_size": 2,
        "has_next": False,
        "has_prev": True,
    }
    assert (
        harness.client.get(
            f"{API}/contacts", params={"page_size": 101}, headers=owner.headers
        ).status_code
        == 422
    )


def test_remove_contact_ends_the_relationship_for_both(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    alice_contact, _ = befriend(harness, alice, bob)
    assert (
        harness.client.delete(f"{API}/contacts/{alice_contact}", headers=alice.headers).status_code
        == 204
    )
    assert contacts(harness, alice) == []
    assert contacts(harness, bob) == []
    # Either side can start again with a fresh request.
    assert request_contact(harness, alice, bob).json()["data"] == {"status": "sent"}


# -- ownership --------------------------------------------------------------------------------


def test_users_cannot_touch_each_others_contact_records(harness: Harness) -> None:
    alice, bob, mallory = make_person(harness), make_person(harness), make_person(harness)
    alice_contact, _ = befriend(harness, alice, bob)
    url = f"{API}/contacts/{alice_contact}"
    assert harness.client.get(url, headers=mallory.headers).status_code == 404
    assert (
        harness.client.patch(url, json={"is_favourite": True}, headers=mallory.headers).status_code
        == 404
    )
    assert harness.client.delete(url, headers=mallory.headers).status_code == 404
    # Nothing changed.
    assert len(contacts(harness, alice)) == 1
    assert contacts(harness, alice)[0]["is_favourite"] is False
    # A contact id from another account is just as unknown to the real counterpart.
    assert harness.client.get(url, headers=bob.headers).status_code == 404


def _as_client(harness: Harness, user_id: str, statement: str, *args: Any) -> list[Any]:
    """Run one statement as the 'authenticated' role with the user's claims (like PostgREST)."""

    async def run() -> list[Any]:
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

    return asyncio.run(run())


def test_rls_blocks_forged_contacts_and_cross_user_reads(harness: Harness) -> None:
    """RLS is the last line of defence behind the service-layer checks."""
    alice, bob, mallory = make_person(harness), make_person(harness), make_person(harness)
    befriend(harness, alice, bob)
    request_contact(harness, alice, mallory)
    harness.client.post(
        f"{API}/contacts/blocks", json={"user_id": mallory.id}, headers=alice.headers
    )
    group = create_group(harness, alice, "Mine")

    # A client may not create a Chikka contact for themselves (only the accept flow does).
    with pytest.raises(asyncpg.PostgresError):
        _as_client(
            harness,
            mallory.id,
            "insert into public.contacts (owner_id, contact_type, contact_user_id)"
            " values ($1, 'chikka', $2)",
            uuid.UUID(mallory.id),
            uuid.UUID(alice.id),
        )
    # Requests and blocks are written only by the backend.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        _as_client(
            harness,
            mallory.id,
            "insert into public.contact_requests (from_user_id, to_user_id) values ($1, $2)",
            uuid.UUID(mallory.id),
            uuid.UUID(bob.id),
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        _as_client(
            harness,
            mallory.id,
            "insert into public.user_blocks (blocker_id, blocked_user_id) values ($1, $2)",
            uuid.UUID(mallory.id),
            uuid.UUID(bob.id),
        )

    # Mallory sees none of Alice's records, and the block against them is invisible to them.
    for table in ("contacts", "contact_groups", "contact_group_members", "user_blocks"):
        rows = _as_client(harness, mallory.id, f"select 1 from public.{table}")  # noqa: S608
        assert rows == [], table
    assert len(_as_client(harness, alice.id, "select 1 from public.user_blocks")) == 1
    assert len(_as_client(harness, alice.id, "select 1 from public.contact_groups")) == 1
    # Only the two parties to a request can read it. Bob is not one of them.
    assert len(_as_client(harness, mallory.id, "select 1 from public.contact_requests")) == 1
    bystander = make_person(harness)
    assert _as_client(harness, bystander.id, "select 1 from public.contact_requests") == []
    assert group["id"]


# -- groups -----------------------------------------------------------------------------------


def create_group(
    harness: Harness, person: Person, name: str, color: str | None = None
) -> dict[str, Any]:
    response = harness.client.post(
        f"{API}/contacts/groups", json={"name": name, "color": color}, headers=person.headers
    )
    assert response.status_code == 201, response.text
    return dict(response.json()["data"])


def test_group_lifecycle(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    alice_contact, _ = befriend(harness, alice, bob)
    family = create_group(harness, alice, "Family", "#aa00ff")
    assert family["color"] == "#AA00FF"
    friends = create_group(harness, alice, "Friends")

    added = harness.client.post(
        f"{API}/contacts/groups/{family['id']}/members",
        json={"contact_ids": [alice_contact]},
        headers=alice.headers,
    )
    assert added.json()["data"]["member_count"] == 1
    # Several groups per contact; adding twice is harmless.
    harness.client.post(
        f"{API}/contacts/groups/{friends['id']}/members",
        json={"contact_ids": [alice_contact, alice_contact]},
        headers=alice.headers,
    )
    assert set(contacts(harness, alice)[0]["group_ids"]) == {family["id"], friends["id"]}
    assert [
        c["user_id"] for c in contacts(harness, alice, filter="group", group_id=family["id"])
    ] == [bob.id]

    renamed = harness.client.patch(
        f"{API}/contacts/groups/{family['id']}", json={"name": "Ohana"}, headers=alice.headers
    )
    assert renamed.json()["data"]["name"] == "Ohana"
    listed = harness.client.get(f"{API}/contacts/groups", headers=alice.headers).json()["data"]
    assert {g["name"]: g["member_count"] for g in listed} == {"Ohana": 1, "Friends": 1}

    assert (
        harness.client.delete(
            f"{API}/contacts/groups/{family['id']}/members/{alice_contact}", headers=alice.headers
        ).status_code
        == 204
    )
    # Deleting a group keeps its contacts.
    assert (
        harness.client.delete(
            f"{API}/contacts/groups/{friends['id']}", headers=alice.headers
        ).status_code
        == 204
    )
    remaining = contacts(harness, alice)
    assert len(remaining) == 1
    assert remaining[0]["group_ids"] == []


def test_group_names_are_unique_per_owner_and_sanitised(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    create_group(harness, alice, "Work")
    duplicate = harness.client.post(
        f"{API}/contacts/groups", json={"name": "WORK"}, headers=alice.headers
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "group_name_taken"
    create_group(harness, bob, "Work")  # A different owner may reuse the name.
    clean = create_group(harness, alice, "<i>School</i>")
    assert clean["name"] == "School"


def test_group_validation(harness: Harness) -> None:
    alice = make_person(harness)
    for body in (
        {"name": ""},
        {"name": "x" * 31},
        {"name": "ok", "color": "red"},
        {"name": "ok", "extra": 1},
    ):
        assert (
            harness.client.post(
                f"{API}/contacts/groups", json=body, headers=alice.headers
            ).status_code
            == 422
        )


def test_group_limit_is_twenty(harness: Harness) -> None:
    alice = make_person(harness)
    for index in range(20):
        create_group(harness, alice, f"Group {index}")
    over = harness.client.post(
        f"{API}/contacts/groups", json={"name": "One too many"}, headers=alice.headers
    )
    assert over.status_code == 422
    assert over.json()["error"]["code"] == "group_limit_reached"


def test_groups_are_private_to_their_owner(harness: Harness) -> None:
    alice, bob, mallory = make_person(harness), make_person(harness), make_person(harness)
    alice_contact, _ = befriend(harness, alice, bob)
    group = create_group(harness, alice, "Secret")
    base = f"{API}/contacts/groups/{group['id']}"
    assert (
        harness.client.get(f"{API}/contacts/groups", headers=mallory.headers).json()["data"] == []
    )
    assert (
        harness.client.patch(base, json={"name": "Hacked"}, headers=mallory.headers).status_code
        == 404
    )
    assert harness.client.delete(base, headers=mallory.headers).status_code == 404
    assert (
        harness.client.post(
            f"{base}/members", json={"contact_ids": [alice_contact]}, headers=mallory.headers
        ).status_code
        == 404
    )
    assert (
        harness.client.get(
            f"{API}/contacts",
            params={"filter": "group", "group_id": group["id"]},
            headers=mallory.headers,
        ).status_code
        == 404
    )


def test_cannot_put_someone_elses_contact_in_your_group(harness: Harness) -> None:
    alice, bob, mallory = make_person(harness), make_person(harness), make_person(harness)
    alice_contact, _ = befriend(harness, alice, bob)
    mine = create_group(harness, mallory, "Mine")
    response = harness.client.post(
        f"{API}/contacts/groups/{mine['id']}/members",
        json={"contact_ids": [alice_contact]},
        headers=mallory.headers,
    )
    assert response.status_code == 404
    rows = harness.sql(
        "select count(*) as n from public.contact_group_members where owner_id = any($1::uuid[])",
        [uuid.UUID(alice.id), uuid.UUID(mallory.id)],
    )
    assert rows[0]["n"] == 0


def test_group_filter_requires_a_group(harness: Harness) -> None:
    alice = make_person(harness)
    response = harness.client.get(
        f"{API}/contacts", params={"filter": "group"}, headers=alice.headers
    )
    assert response.status_code == 422


def test_removing_a_contact_drops_its_group_memberships(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    alice_contact, _ = befriend(harness, alice, bob)
    group = create_group(harness, alice, "Pals")
    harness.client.post(
        f"{API}/contacts/groups/{group['id']}/members",
        json={"contact_ids": [alice_contact]},
        headers=alice.headers,
    )
    harness.client.delete(f"{API}/contacts/{alice_contact}", headers=alice.headers)
    listed = harness.client.get(f"{API}/contacts/groups", headers=alice.headers).json()["data"]
    assert listed[0]["member_count"] == 0


# -- recent -----------------------------------------------------------------------------------


def conversation_between(harness: Harness, first: Person, second: Person, minutes_ago: int) -> str:
    rows = harness.sql(
        "select private.get_or_create_chikka_conversation($1, $2) as id",
        uuid.UUID(first.id),
        uuid.UUID(second.id),
    )
    conversation_id = rows[0]["id"]
    harness.sql(
        "update public.conversations set last_message_at = now() - make_interval(mins => $2)"
        " where id = $1",
        conversation_id,
        minutes_ago,
    )
    return str(conversation_id)


def test_recent_contacts_are_ordered_by_latest_activity(harness: Harness) -> None:
    owner = make_person(harness)
    older, newer, silent = make_person(harness), make_person(harness), make_person(harness)
    for friend in (older, newer, silent):
        befriend(harness, owner, friend)
    conversation_between(harness, owner, older, 60)
    newest = conversation_between(harness, owner, newer, 5)

    response = harness.client.get(f"{API}/contacts/recent", headers=owner.headers)
    recent = response.json()["data"]
    assert [r["contact"]["user_id"] for r in recent] == [newer.id, older.id]
    assert recent[0]["conversation_id"] == newest
    assert "body" not in response.text  # No message content is exposed here.


def test_recent_excludes_blocked_contacts_and_clearing_keeps_conversations(
    harness: Harness,
) -> None:
    owner, kept, blocked = make_person(harness), make_person(harness), make_person(harness)
    befriend(harness, owner, kept)
    befriend(harness, owner, blocked)
    conversation_between(harness, owner, kept, 10)
    conversation_between(harness, owner, blocked, 5)
    harness.client.post(
        f"{API}/contacts/blocks", json={"user_id": blocked.id}, headers=owner.headers
    )

    recent = harness.client.get(f"{API}/contacts/recent", headers=owner.headers).json()["data"]
    assert [r["contact"]["user_id"] for r in recent] == [kept.id]

    assert harness.client.delete(f"{API}/contacts/recent", headers=owner.headers).status_code == 204
    assert harness.client.get(f"{API}/contacts/recent", headers=owner.headers).json()["data"] == []
    kept_threads = harness.sql(
        "select count(*) as n from public.conversation_members where user_id = $1",
        uuid.UUID(owner.id),
    )
    assert kept_threads[0]["n"] == 2


def test_recent_conversations_cover_contacts_strangers_and_sms(harness: Harness) -> None:
    owner, friend, stranger = (
        make_person(harness),
        make_person(harness, "Pal"),
        make_person(harness, "Stranger"),
    )
    befriend(harness, owner, friend)
    conversation_between(harness, owner, friend, 30)
    conversation_between(harness, owner, stranger, 20)
    sms = harness.sql(
        "select private.get_or_create_sms_conversation($1, $2) as id",
        uuid.UUID(owner.id),
        FAKE_PHONE,
    )[0]["id"]
    harness.sql(
        "update public.conversations set last_message_at = now() - interval '1 minute'"
        " where id = $1",
        sms,
    )

    response = harness.client.get(f"{API}/contacts/recent-conversations", headers=owner.headers)
    data = response.json()["data"]
    assert [d["conversation_type"] for d in data] == ["sms", "chikka", "chikka"]
    assert data[0]["masked_phone"] == "+63****4567"
    assert FAKE_PHONE not in response.text
    assert [d["is_contact"] for d in data] == [False, False, True]
    assert data[2]["display_name"] == "Pal"


def test_recent_conversations_hide_blocked_people(harness: Harness) -> None:
    owner, other = make_person(harness), make_person(harness)
    conversation_between(harness, owner, other, 5)
    harness.client.post(f"{API}/contacts/blocks", json={"user_id": other.id}, headers=owner.headers)
    assert (
        harness.client.get(f"{API}/contacts/recent-conversations", headers=owner.headers).json()[
            "data"
        ]
        == []
    )
    # The blocked person does not see the blocker either.
    assert (
        harness.client.get(f"{API}/contacts/recent-conversations", headers=other.headers).json()[
            "data"
        ]
        == []
    )


# -- privacy settings and audit ---------------------------------------------------------------


def test_privacy_defaults_are_conservative(harness: Harness) -> None:
    alice = make_person(harness)
    data = harness.client.get(f"{API}/users/me/privacy", headers=alice.headers).json()["data"]
    assert data == {
        "profile_visibility": "contacts",
        "share_presence": "contacts",
        "show_last_seen": False,
        "discoverable_by_email": False,
        "discoverable_by_phone": False,
    }


def test_privacy_update_validation(harness: Harness) -> None:
    alice = make_person(harness)
    for body in (
        {"profile_visibility": "public"},
        {"discoverable_by_email": None},
        {"unknown_field": True},
    ):
        assert (
            harness.client.patch(
                f"{API}/users/me/privacy", json=body, headers=alice.headers
            ).status_code
            == 422
        )


def test_contact_decisions_are_audited_without_personal_data(harness: Harness) -> None:
    alice, bob = make_person(harness), make_person(harness)
    befriend(harness, alice, bob)
    harness.client.post(f"{API}/contacts/blocks", json={"user_id": bob.id}, headers=alice.headers)
    harness.client.delete(f"{API}/contacts/blocks/{bob.id}", headers=alice.headers)
    actions = {
        row["action"]
        for row in harness.sql("select action from public.audit_logs where category = 'privacy'")
    }
    assert {
        "contact.request_sent",
        "contact.request_accepted",
        "contact.blocked",
        "contact.unblocked",
    } <= actions
    metadata = " ".join(
        str(row["metadata"]) for row in harness.sql("select metadata from public.audit_logs")
    )
    assert alice.email not in metadata
    assert bob.email not in metadata
