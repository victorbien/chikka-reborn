"""Module G: notifications against the real database, the real worker loop body and the mock email
provider. Nothing is emailed for real."""

import uuid
from datetime import timedelta
from typing import Any, cast

from app.integrations.email.base import EmailError
from app.integrations.email.mock import MockEmailProvider
from app.modules.notifications.dispatcher import NotificationDispatcher
from tests.flows.conftest import Harness
from tests.flows.test_chat import of_type, open_conversation, send, socket, sync
from tests.flows.test_contacts import Person, befriend, incoming, make_person, request_contact
from tests.flows.test_sms import admin_user, ready_to_send
from tests.flows.test_sms import send as send_sms

API = "/api/v1/notifications"


def dispatcher(harness: Harness) -> NotificationDispatcher:
    return cast(NotificationDispatcher, harness.client.app.state.notification_dispatcher)  # type: ignore[attr-defined]


def mailbox(harness: Harness) -> MockEmailProvider:
    return cast(MockEmailProvider, harness.client.app.state.providers.email)  # type: ignore[attr-defined]


def dispatch(harness: Harness) -> tuple[int, int]:
    """One pass of the delivery worker (the background loop is off in tests)."""
    return cast(tuple[int, int], harness.client.portal.call(dispatcher(harness).run_once))  # type: ignore[union-attr]


def feed(harness: Harness, person: Person, **params: Any) -> list[dict[str, Any]]:
    response = harness.client.get(API, params=params, headers=person.headers)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["data"]
    return items


def unread(harness: Harness, person: Person) -> int:
    response = harness.client.get(f"{API}/unread-count", headers=person.headers)
    assert response.status_code == 200, response.text
    return int(response.json()["data"]["unread_count"])


def prefs(harness: Harness, person: Person, body: dict[str, Any] | None = None) -> Any:
    if body is None:
        return harness.client.get(f"{API}/preferences", headers=person.headers)
    return harness.client.put(f"{API}/preferences", json=body, headers=person.headers)


def chatting(harness: Harness) -> tuple[Person, Person, str]:
    alice, bob = make_person(harness, "Alice Reyes"), make_person(harness, "Bob Cruz")
    befriend(harness, alice, bob)
    # Becoming contacts notifies both people. Start the scenario from an empty feed.
    harness.sql(
        "delete from public.notifications where user_id = any($1::uuid[])",
        [uuid.UUID(alice.id), uuid.UUID(bob.id)],
    )
    return alice, bob, str(open_conversation(harness, alice, bob)["id"])


def announce(
    harness: Harness,
    admin: dict[str, str],
    user_id: str | None,
    key: str | None = None,
    **extra: Any,
) -> Any:
    return harness.client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "Scheduled maintenance",
            "body": "Tonight at 10pm.",
            "user_id": user_id,
            **extra,
        },
        headers={**admin, "Idempotency-Key": key or str(uuid.uuid4())},
    )


# -- creation, unread count, read state -----------------------------------------------------------


def test_a_new_message_creates_one_unread_notification_without_the_text(harness: Harness) -> None:
    alice, bob, conversation = chatting(harness)

    assert send(harness, bob, conversation, "Lunch tomorrow? My number is private").status_code in (
        200,
        201,
    )

    message = next(i for i in feed(harness, alice) if i["type"] == "new_message")
    assert message["title"] == "New message from Bob Cruz"
    assert message["body"] is None  # previews are off by default
    assert message["is_read"] is False and message["reference_type"] == "conversation"
    assert message["reference_id"] == conversation
    assert unread(harness, alice) == 1
    # The sender is never notified about their own message.
    assert [i for i in feed(harness, bob) if i["type"] == "new_message"] == []


def test_messages_in_one_chat_fold_into_one_notification_until_it_is_read(harness: Harness) -> None:
    alice, bob, conversation = chatting(harness)

    for text in ("one", "two", "three"):
        send(harness, bob, conversation, text)

    rows = [i for i in feed(harness, alice) if i["type"] == "new_message"]
    assert len(rows) == 1 and rows[0]["occurrence_count"] == 3
    assert unread(harness, alice) == 1

    harness.client.post(f"{API}/{rows[0]['id']}/read", headers=alice.headers)
    send(harness, bob, conversation, "four")

    rows = [i for i in feed(harness, alice) if i["type"] == "new_message"]
    assert [r["occurrence_count"] for r in rows] == [1, 3]  # a fresh one, newest first
    assert unread(harness, alice) == 1


def test_mark_one_as_read_then_all_as_read(harness: Harness) -> None:
    alice, bob, conversation = chatting(harness)
    send(harness, bob, conversation, "hello")
    request_contact(harness, make_person(harness, "Carol"), alice)
    assert unread(harness, alice) == 2
    first = feed(harness, alice)[0]

    one = harness.client.post(f"{API}/{first['id']}/read", headers=alice.headers)
    again = harness.client.post(f"{API}/{first['id']}/read", headers=alice.headers)

    assert one.json()["data"]["is_read"] is True and again.status_code == 200
    assert unread(harness, alice) == 1
    only_unread = feed(harness, alice, unread_only="true")
    assert len(only_unread) == 1 and only_unread[0]["id"] != first["id"]

    done = harness.client.post(f"{API}/read-all", headers=alice.headers).json()["data"]
    assert done == {"updated": 1, "unread_count": 0}
    assert feed(harness, alice, unread_only="true") == []
    assert (
        harness.client.post(f"{API}/read-all", headers=alice.headers).json()["data"]["updated"] == 0
    )


def test_read_all_can_be_limited_to_one_type(harness: Harness) -> None:
    alice, bob, conversation = chatting(harness)
    send(harness, bob, conversation, "hello")
    request_contact(harness, make_person(harness, "Carol"), alice)

    done = harness.client.post(
        f"{API}/read-all", params={"type": "new_message"}, headers=alice.headers
    )

    assert done.json()["data"] == {"updated": 1, "unread_count": 1}
    assert [i["type"] for i in feed(harness, alice, unread_only="true")] == ["contact_request"]
    assert [i["type"] for i in feed(harness, alice, type="new_message")] == ["new_message"]


def test_dismissed_notifications_leave_the_feed_and_the_count(harness: Harness) -> None:
    alice, bob, conversation = chatting(harness)
    send(harness, bob, conversation, "hello")
    note = next(i for i in feed(harness, alice) if i["type"] == "new_message")

    gone = harness.client.post(f"{API}/{note['id']}/dismiss", headers=alice.headers)

    assert gone.status_code == 200 and gone.json()["data"]["unread_count"] == 0
    assert [i for i in feed(harness, alice) if i["id"] == note["id"]] == []


def test_the_feed_is_paginated_and_private(harness: Harness) -> None:
    alice = make_person(harness, "Alice")
    admin, _ = admin_user(harness)
    for index in range(3):
        assert announce(harness, admin, alice.id, body=f"Notice {index}").status_code == 200
    mallory = make_person(harness, "Mallory")

    page = harness.client.get(API, params={"page_size": 2}, headers=alice.headers).json()

    assert page["pagination"]["total"] == 3 and page["pagination"]["has_next"] is True
    assert len(page["data"]) == 2
    assert feed(harness, mallory) == [] and unread(harness, mallory) == 0
    other_users_note = page["data"][0]["id"]
    for path in (f"{API}/{other_users_note}/read", f"{API}/{other_users_note}/dismiss"):
        assert harness.client.post(path, headers=mallory.headers).status_code == 404, path
    assert (
        harness.client.post(f"{API}/{uuid.uuid4()}/read", headers=alice.headers).status_code == 404
    )
    assert unread(harness, alice) == 3  # mallory's attempts changed nothing


def test_notification_endpoints_need_a_signed_in_user(harness: Harness) -> None:
    for method, path in (
        ("get", API),
        ("get", f"{API}/unread-count"),
        ("post", f"{API}/read-all"),
        ("get", f"{API}/preferences"),
        ("put", f"{API}/preferences"),
        ("post", f"{API}/{uuid.uuid4()}/read"),
    ):
        assert getattr(harness.client, method)(path).status_code == 401, path


# -- other event sources -----------------------------------------------------------------------


def test_contact_requests_and_acceptances_notify_once(harness: Harness) -> None:
    alice, bob = make_person(harness, "Alice Reyes"), make_person(harness, "Bob Cruz")

    request_contact(harness, alice, bob)
    request_contact(harness, alice, bob)  # a duplicate request changes nothing
    asked = [i for i in feed(harness, bob) if i["type"] == "contact_request"]
    assert [a["title"] for a in asked] == ["Alice Reyes sent you a contact request"]

    pending = incoming(harness, bob)
    harness.client.post(f"/api/v1/contacts/requests/{pending[0]['id']}/accept", headers=bob.headers)
    accepted = [i for i in feed(harness, alice) if i["type"] == "contact_accepted"]
    assert [a["title"] for a in accepted] == ["Bob Cruz accepted your contact request"]


def test_a_muted_conversation_does_not_notify(harness: Harness) -> None:
    alice, bob, conversation = chatting(harness)
    harness.sql(
        "update public.conversation_members set muted_indefinitely = true "
        "where conversation_id = $1 and user_id = $2",
        uuid.UUID(conversation),
        uuid.UUID(alice.id),
    )

    send(harness, bob, conversation, "hello?")

    assert [i for i in feed(harness, alice) if i["type"] == "new_message"] == []


def test_a_delivered_sms_notifies_once_even_when_the_callback_repeats(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    me = Person("", headers, user_id, "")
    sent = send_sms(harness, headers).json()["data"]
    for _ in range(4):
        harness.clock.advance(3)
        harness.run_worker()

    delivered = [i for i in feed(harness, me) if i["type"] == "sms_delivered"]
    assert len(delivered) == 1 and delivered[0]["reference_id"] == sent["id"]
    assert delivered[0]["title"].startswith("Simulated SMS")
    assert delivered[0]["body"] is None  # SMS text is never copied into notifications


def test_signing_out_other_devices_creates_a_security_notice(harness: Harness) -> None:
    alice = make_person(harness, "Alice Reyes")
    second = harness.login(alice.email).json()["data"]["access_token"]
    device = Person(alice.email, {"Authorization": f"Bearer {second}"}, alice.id, alice.username)

    assert (
        harness.client.post(
            "/api/v1/auth/sessions/revoke-others", headers=device.headers
        ).status_code
        == 200
    )

    notes = [i for i in feed(harness, device) if i["type"] == "security"]
    assert [n["title"] for n in notes] == ["You signed out of your other devices"]
    assert "other session(s) were ended from this account" in notes[0]["body"]
    # Security notices are always emailed by default and can never be hidden from the feed.
    refused = prefs(harness, device, {"types": {"security": {"in_app": False}}})
    assert refused.status_code == 422


# -- preferences -------------------------------------------------------------------------------


def test_preferences_start_at_the_defaults(harness: Harness) -> None:
    alice = make_person(harness, "Alice")

    data = prefs(harness, alice).json()["data"]

    types = {t["type"]: t for t in data["types"]}
    assert set(types) == {
        "new_message",
        "sms_inbound",
        "sms_delivered",
        "sms_failed",
        "contact_request",
        "contact_accepted",
        "low_balance",
        "system",
        "security",
    }
    assert types["new_message"] == {
        "type": "new_message",
        "in_app": True,
        "push": True,
        "email": False,
        "in_app_locked": False,
    }
    assert types["sms_delivered"]["push"] is False
    assert types["security"]["email"] is True and types["security"]["in_app_locked"] is True
    assert all(types[t]["in_app_locked"] for t in ("sms_failed", "system", "security"))
    assert (data["quiet_hours_start"], data["quiet_hours_end"]) == (None, None)
    assert data["show_previews"] is False
    assert (
        data["low_balance_threshold_units"] == 500 and data["low_balance_threshold_credits"] == 5.0
    )
    assert data["email_simulated"] is True and data["email_disabled"] is False


def test_preferences_store_only_deviations_and_validate(harness: Harness) -> None:
    alice = make_person(harness, "Alice")

    saved = prefs(
        harness,
        alice,
        {
            "types": {
                "new_message": {"email": True, "push": False},
                "contact_request": {"push": True},
            },
            "show_previews": True,
            "low_balance_threshold_units": 1000,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
        },
    )

    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    types = {t["type"]: t for t in data["types"]}
    assert (types["new_message"]["email"], types["new_message"]["push"]) == (True, False)
    assert (data["quiet_hours_start"], data["quiet_hours_end"]) == ("22:00", "07:00")
    assert data["show_previews"] is True and data["low_balance_threshold_credits"] == 10.0
    stored = harness.sql(
        "select overrides::text as o from public.notification_preferences where user_id = $1",
        uuid.UUID(alice.id),
    )[0]["o"]
    assert '"new_message.email": true' in stored and '"new_message.push": false' in stored
    assert "contact_request" not in stored  # equal to the default: nothing stored

    for bad in (
        {"low_balance_threshold_units": 99},
        {"low_balance_threshold_units": 10_001},
        {"quiet_hours_start": "22:00"},
        {"types": {"bogus": {"email": True}}},
        {"types": {"new_message": {"carrier_pigeon": True}}},
        {"unknown_field": 1},
    ):
        assert prefs(harness, alice, bad).status_code == 422, bad
    assert (
        prefs(harness, alice, {"quiet_hours_start": None, "quiet_hours_end": None}).json()["data"][
            "quiet_hours_start"
        ]
        is None
    )


def test_mandatory_notices_cannot_be_switched_off_in_the_app(harness: Harness) -> None:
    alice = make_person(harness, "Alice")

    for kind in ("sms_failed", "system", "security"):
        refused = prefs(harness, alice, {"types": {kind: {"in_app": False}}})
        assert refused.status_code == 422, kind
        assert refused.json()["error"]["code"] == "notification_mandatory"
    # Their other channels can still be changed.
    assert prefs(harness, alice, {"types": {"system": {"email": False}}}).status_code == 200


def test_a_type_switched_off_everywhere_creates_nothing(harness: Harness) -> None:
    alice, bob = make_person(harness, "Alice"), make_person(harness, "Bob")
    prefs(harness, alice, {"types": {"contact_request": {"in_app": False, "push": False}}})

    request_contact(harness, bob, alice)

    assert feed(harness, alice) == [] and unread(harness, alice) == 0
    assert (
        harness.sql("select 1 from public.notifications where user_id = $1", uuid.UUID(alice.id))
        == []
    )


def test_in_app_off_hides_the_notice_but_keeps_the_other_channels(harness: Harness) -> None:
    alice, bob, conversation = chatting(harness)
    prefs(harness, alice, {"types": {"new_message": {"in_app": False, "email": True}}})

    send(harness, bob, conversation, "hello")

    assert feed(harness, alice) == [] and unread(harness, alice) == 0
    row = harness.sql(
        "select email_requested_at, dismissed_at from public.notifications where user_id = $1",
        uuid.UUID(alice.id),
    )
    assert len(row) == 1 and row[0]["email_requested_at"] is not None
    assert row[0]["dismissed_at"] is not None


def test_previews_show_message_text_only_when_enabled(harness: Harness) -> None:
    alice, bob, conversation = chatting(harness)
    prefs(harness, alice, {"show_previews": True})

    send(harness, bob, conversation, "Dinner at 7?")

    note = next(i for i in feed(harness, alice) if i["type"] == "new_message")
    assert note["body"] == "Dinner at 7?"


# -- delivery: live events, browser flag, email, quiet hours --------------------------------------


def test_a_new_notification_is_pushed_to_open_sessions_with_the_browser_flag(
    harness: Harness,
) -> None:
    alice, bob, conversation = chatting(harness)
    dispatch(harness)  # clear anything announced during setup
    with socket(harness, alice) as ws:
        send(harness, bob, conversation, "ping")

        announced, _ = dispatch(harness)
        frames = of_type(sync(ws), "notification.created")

    assert announced >= 1 and len(frames) == 1
    data = frames[0]["data"]
    assert data["notification"]["type"] == "new_message"
    assert data["notification"]["title"] == "New message from Bob Cruz"
    assert data["browser"] is True and data["unread_count"] == 1
    assert dispatch(harness)[0] == 0  # announced exactly once


def test_browser_notifications_follow_the_push_preference(harness: Harness) -> None:
    alice, bob, conversation = chatting(harness)
    prefs(harness, alice, {"types": {"new_message": {"push": False}}})
    dispatch(harness)
    with socket(harness, alice) as ws:
        send(harness, bob, conversation, "ping")
        dispatch(harness)
        frames = of_type(sync(ws), "notification.created")

    assert len(frames) == 1 and frames[0]["data"]["browser"] is False
    assert unread(harness, alice) == 1  # still in the feed


def test_quiet_hours_silence_browser_and_email_but_not_the_feed(harness: Harness) -> None:
    alice = make_person(harness, "Alice")
    admin, _ = admin_user(harness)
    now = harness.clock.now
    start = (now - timedelta(hours=1)).strftime("%H:%M")
    end = (now + timedelta(hours=1)).strftime("%H:%M")
    prefs(harness, alice, {"quiet_hours_start": start, "quiet_hours_end": end})
    mailbox(harness).outbox.clear()

    assert announce(harness, admin, alice.id).status_code == 200
    dispatch(harness)

    note = feed(harness, alice)[0]
    assert note["type"] == "system"
    row = harness.sql(
        "select browser_push, email_requested_at from public.notifications where id = $1",
        uuid.UUID(note["id"]),
    )[0]
    assert row["browser_push"] is False and row["email_requested_at"] is None
    assert mailbox(harness).outbox == []


def test_system_notices_are_emailed_once_through_the_configured_provider(harness: Harness) -> None:
    alice = make_person(harness, "Alice")
    admin, _ = admin_user(harness)
    mailbox(harness).outbox.clear()

    assert announce(harness, admin, alice.id).status_code == 200
    first = dispatch(harness)
    second = dispatch(harness)

    assert first[1] == 1 and second == (0, 0)
    (sent,) = mailbox(harness).outbox
    assert sent.to == alice.email
    assert sent.subject == "Chikka Reborn: Scheduled maintenance"
    assert "Tonight at 10pm." in sent.text and "/notifications" in sent.text
    assert "Simulated email" in sent.text


def test_email_is_off_by_default_for_chat_messages(harness: Harness) -> None:
    _alice, bob, conversation = chatting(harness)
    mailbox(harness).outbox.clear()

    send(harness, bob, conversation, "hello")
    dispatch(harness)

    assert mailbox(harness).outbox == []


def test_a_failed_email_is_retried_later_and_gives_up_after_three_attempts(
    harness: Harness,
) -> None:
    alice = make_person(harness, "Alice")
    admin, _ = admin_user(harness)
    mailbox(harness).outbox.clear()
    mailbox(harness).fail_next(EmailError("down"), EmailError("down"))
    assert announce(harness, admin, alice.id).status_code == 200

    assert dispatch(harness)[1] == 0  # attempt 1 fails
    assert dispatch(harness)[1] == 0  # too soon to retry
    harness.clock.advance(61)
    assert dispatch(harness)[1] == 0  # attempt 2 fails
    harness.clock.advance(121)
    assert dispatch(harness)[1] == 1  # attempt 3 succeeds

    assert len(mailbox(harness).outbox) == 1
    row = harness.sql(
        "select email_attempts, email_sent_at from public.notifications where user_id = $1",
        uuid.UUID(alice.id),
    )[0]
    assert row["email_attempts"] == 3 and row["email_sent_at"] is not None


def test_a_rejected_address_is_not_retried_and_eventually_disables_email(harness: Harness) -> None:
    alice = make_person(harness, "Alice")
    admin, _ = admin_user(harness)
    mailbox(harness).outbox.clear()
    for _ in range(3):
        mailbox(harness).fail_next(EmailError("no such mailbox", permanent=True))
        assert announce(harness, admin, alice.id).status_code == 200
        dispatch(harness)

    assert mailbox(harness).outbox == []
    state = harness.sql(
        "select email_hard_bounce_count as n, email_disabled_at from "
        "public.notification_preferences where user_id = $1",
        uuid.UUID(alice.id),
    )[0]
    assert state["n"] == 3 and state["email_disabled_at"] is not None
    assert prefs(harness, alice).json()["data"]["email_disabled"] is True
    # Notices still reach the feed; they just are not emailed any more.
    assert announce(harness, admin, alice.id).status_code == 200
    dispatch(harness)
    assert mailbox(harness).outbox == [] and len(feed(harness, alice)) == 4


# -- administration -------------------------------------------------------------------------------


def test_only_administrators_can_send_notices(harness: Harness) -> None:
    alice = make_person(harness, "Alice")
    bob = make_person(harness, "Bob")

    refused = announce(harness, alice.headers, bob.id)
    anonymous = harness.client.post(
        "/api/v1/admin/notifications",
        json={"title": "Hi", "user_id": bob.id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    assert refused.status_code == 403 and anonymous.status_code == 401
    assert feed(harness, bob) == []


def test_an_admin_notice_is_idempotent_and_audited(harness: Harness) -> None:
    alice = make_person(harness, "Alice")
    admin, admin_id = admin_user(harness)
    key = str(uuid.uuid4())

    first = announce(harness, admin, alice.id, key=key)
    again = announce(harness, admin, alice.id, key=key)

    assert first.json()["data"] == {"recipients": 1, "created": 1}
    assert again.json()["data"] == {"recipients": 1, "created": 0}
    assert len(feed(harness, alice)) == 1
    audit = harness.sql(
        "select actor_id from public.audit_logs where action = 'notification.announced' "
        "and metadata->>'key' = $1",
        key,
    )
    assert len(audit) == 2 and {str(a["actor_id"]) for a in audit} == {admin_id}


def test_a_notice_can_go_to_everyone_and_to_nobody_unknown(harness: Harness) -> None:
    alice = make_person(harness, "Alice")
    admin, _ = admin_user(harness)

    everyone = announce(harness, admin, None)
    unknown = announce(harness, admin, str(uuid.uuid4()))
    invalid = announce(harness, admin, alice.id, title="")

    active = harness.sql("select count(*) as n from public.profiles where status = 'active'")[0][
        "n"
    ]
    assert everyone.json()["data"]["recipients"] == active
    assert [i["title"] for i in feed(harness, alice)] == ["Scheduled maintenance"]
    assert unknown.status_code == 404
    assert invalid.status_code == 422
