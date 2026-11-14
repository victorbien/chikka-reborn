"""Module H: simulated SMS credits against the real database and the real SMS worker.

Simulated messages charge the separate demo ledger. The ledger is append-only, every change is
idempotent per message, and nothing here is money.
"""

import uuid
from typing import Any

import pytest

from tests.flows.conftest import Harness
from tests.flows.test_sms import (
    NUMBER,
    admin_user,
    message,
    pump,
    ready_to_send,
    send,
    sms_user,
)

API = "/api/v1/credits"
START = 5000  # demo_grant_units: 50 credits


def balance(harness: Harness, headers: dict[str, str]) -> dict[str, Any]:
    response = harness.client.get(API, headers=headers)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


def demo(harness: Harness, headers: dict[str, str]) -> dict[str, Any]:
    ledger: dict[str, Any] = next(
        item for item in balance(harness, headers)["ledgers"] if item["ledger"] == "demo"
    )
    return ledger


def history(harness: Harness, headers: dict[str, str], **params: Any) -> list[dict[str, Any]]:
    response = harness.client.get(f"{API}/transactions", params=params, headers=headers)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["data"]
    return items


def entries(harness: Harness, message_id: str) -> list[tuple[str, str]]:
    rows = harness.sql(
        "select ledger_type, entry_type from public.credit_transactions "
        "where message_id = $1 order by created_at, id",
        uuid.UUID(message_id),
    )
    return [(r["ledger_type"], r["entry_type"]) for r in rows]


def quote_cost(harness: Harness, headers: dict[str, str], to: str = NUMBER) -> int:
    response = harness.client.post(
        "/api/v1/sms/quote", json={"to": to, "body": "Kumusta ka, Nanay?"}, headers=headers
    )
    assert response.status_code == 200, response.text
    return int(response.json()["data"]["cost"]["units"])


def adjust(
    harness: Harness,
    headers: dict[str, str],
    user_id: str,
    amount: int,
    *,
    key: str | None = None,
    reason: str = "Demo top-up for testing",
    **extra: Any,
) -> Any:
    return harness.client.post(
        "/api/v1/admin/credits/adjustments",
        json={"user_id": user_id, "amount_units": amount, "reason": reason, **extra},
        headers={**headers, "Idempotency-Key": key or str(uuid.uuid4())},
    )


# -- balance and cost preview -------------------------------------------------------------------


def test_new_users_start_with_demo_credits_and_a_clear_notice(harness: Harness) -> None:
    headers, _ = sms_user(harness)

    data = balance(harness, headers)

    ledgers = {item["ledger"]: item for item in data["ledgers"]}
    assert ledgers["demo"]["available_units"] == START
    assert ledgers["demo"]["available_credits"] == 50.0
    assert ledgers["live"]["available_units"] == 0 and ledgers["live"]["charges_apply"] is False
    assert data["active_ledger"] == "demo" and data["is_simulated"] is True
    assert "not money" in data["notice"]
    first = history(harness, headers)[0]
    assert (first["entry_type"], first["balance_delta"], first["balance_after"]) == (
        "grant",
        START,
        START,
    )


def test_the_quote_shows_the_cost_and_whether_you_can_afford_it(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)

    quote = harness.client.post(
        "/api/v1/sms/quote", json={"to": NUMBER, "body": "Hello"}, headers=headers
    ).json()["data"]

    assert quote["cost"]["units"] > 0
    hint = quote["balance"]
    assert hint["ledger"] == "demo" and hint["is_simulated"] is True
    assert hint["available_units"] == START and hint["sufficient"] is True
    assert hint["charges_apply"] is True and hint["is_low"] is False
    assert quote["can_send"] is True


# -- charging ------------------------------------------------------------------------------------


def test_a_delivered_sms_holds_then_spends_exactly_its_cost(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    cost = quote_cost(harness, headers)

    sent = send(harness, headers).json()["data"]
    assert (demo(harness, headers)["reserved_units"], demo(harness, headers)["balance_units"]) == (
        cost,
        START,
    )
    pump(harness)
    pump(harness, seconds=3)

    ledger = demo(harness, headers)
    assert (ledger["balance_units"], ledger["reserved_units"]) == (START - cost, 0)
    assert entries(harness, sent["id"]) == [("demo", "reservation"), ("demo", "deduction")]
    assert message(harness, headers, sent["id"])["status"] in ("sent", "delivered")
    deduction = next(t for t in history(harness, headers) if t["entry_type"] == "deduction")
    assert deduction["credits_delta"] == -cost / 100
    assert deduction["balance_after"] == START - cost
    assert deduction["message_id"] == sent["id"] and deduction["provider"] == "mock"
    assert deduction["segment_count"] == 1


def test_live_credits_are_never_touched_by_a_simulated_send(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)

    send(harness, headers)
    pump(harness)

    live = harness.sql(
        "select balance_units, reserved_units from public.messaging_credits "
        "where user_id = $1 and ledger_type = 'live'",
        uuid.UUID(user_id),
    )[0]
    assert (live["balance_units"], live["reserved_units"]) == (0, 0)
    assert (
        harness.sql(
            "select 1 from public.credit_transactions where user_id = $1 and ledger_type = 'live'",
            uuid.UUID(user_id),
        )
        == []
    )


def test_a_repeated_send_with_the_same_key_is_charged_once(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    cost = quote_cost(harness, headers)
    key = str(uuid.uuid4())

    first = send(harness, headers, key=key)
    second = send(harness, headers, key=key)
    pump(harness, seconds=3)

    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert demo(harness, headers)["balance_units"] == START - cost
    assert entries(harness, first.json()["data"]["id"]) == [
        ("demo", "reservation"),
        ("demo", "deduction"),
    ]


def test_a_message_accepted_then_failed_is_refunded_once(harness: Harness) -> None:
    number = "+12025550101"  # simulated scenario: accepted, then the carrier reports failure
    headers, _ = ready_to_send(harness, number)
    cost = quote_cost(harness, headers, number)

    sent = send(harness, headers, to=number).json()["data"]
    pump(harness)
    pump(harness, seconds=3)
    pump(harness, seconds=3)

    assert message(harness, headers, sent["id"])["status"] == "failed"
    assert entries(harness, sent["id"]) == [
        ("demo", "reservation"),
        ("demo", "deduction"),
        ("demo", "refund"),
    ]
    ledger = demo(harness, headers)
    assert (ledger["balance_units"], ledger["reserved_units"]) == (START, 0)
    refund = next(t for t in history(harness, headers) if t["entry_type"] == "refund")
    assert refund["balance_delta"] == cost
    # More worker passes and repeated callbacks cannot refund again.
    pump(harness, steps=3, seconds=60)
    assert demo(harness, headers)["balance_units"] == START


def test_a_message_that_was_never_accepted_only_releases_its_hold(harness: Harness) -> None:
    number = "+12025550104"  # simulated scenario: every send attempt fails transiently
    headers, _ = ready_to_send(harness, number)

    sent = send(harness, headers, to=number).json()["data"]
    assert demo(harness, headers)["reserved_units"] > 0
    for _ in range(6):
        pump(harness, seconds=400)

    assert message(harness, headers, sent["id"])["status"] == "failed"
    assert entries(harness, sent["id"]) == [
        ("demo", "reservation"),
        ("demo", "reservation_release"),
    ]
    ledger = demo(harness, headers)
    assert (ledger["balance_units"], ledger["reserved_units"]) == (START, 0)


def test_retrying_a_failed_message_charges_the_new_message_once(harness: Harness) -> None:
    number = "+12025550101"
    headers, _ = ready_to_send(harness, number)
    sent = send(harness, headers, to=number).json()["data"]
    pump(harness)
    pump(harness, seconds=3)
    pump(harness, seconds=3)
    assert demo(harness, headers)["balance_units"] == START

    again = harness.client.post(
        f"/api/v1/sms/messages/{sent['id']}/retry",
        json={"confirmed": True},
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )

    assert again.status_code == 202, again.text
    assert entries(harness, again.json()["data"]["id"]) == [("demo", "reservation")]


# -- not enough credits ----------------------------------------------------------------------------


def test_insufficient_credits_block_the_quote_and_the_send(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    admin, _ = _admin(harness)
    cost = quote_cost(harness, headers)
    assert adjust(harness, admin, user_id, -(START - cost + 1)).status_code == 200  # leave cost-1
    messages_before = harness.sql("select count(*) as n from public.messages")[0]["n"]

    quote = harness.client.post(
        "/api/v1/sms/quote", json={"to": NUMBER, "body": "Hello"}, headers=headers
    ).json()["data"]
    refused = send(harness, headers)

    assert quote["can_send"] is False
    assert quote["balance"]["sufficient"] is False
    assert "insufficient_credits" in {b["code"] for b in quote["blockers"]}
    assert refused.status_code == 402
    assert refused.json()["error"]["code"] == "insufficient_credits"
    assert harness.sql("select count(*) as n from public.messages")[0]["n"] == messages_before
    assert demo(harness, headers)["balance_units"] == cost - 1


def test_two_sends_cannot_both_spend_the_last_credits(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    admin, _ = _admin(harness)
    cost = quote_cost(harness, headers)
    assert adjust(harness, admin, user_id, -(START - cost)).status_code == 200  # exactly one send

    first = send(harness, headers, body="First message")
    second = send(harness, headers, body="Second message")

    assert first.status_code == 202
    assert second.status_code == 402
    ledger = demo(harness, headers)
    assert (ledger["balance_units"], ledger["reserved_units"]) == (cost, cost)


# -- low balance ---------------------------------------------------------------------------------


def low_balance_notices(harness: Harness, user_id: str) -> list[Any]:
    return harness.sql(
        "select title, body from public.notifications "
        "where user_id = $1 and notification_type = 'low_balance'",
        uuid.UUID(user_id),
    )


def test_low_balance_is_announced_once_per_crossing(harness: Harness) -> None:
    headers, user_id = ready_to_send(harness)
    admin, _ = _admin(harness)
    cost = quote_cost(harness, headers)
    # Leave room for exactly two sends above the default threshold of 500 units.
    assert adjust(harness, admin, user_id, -(START - 500 - cost - cost // 2)).status_code == 200

    send(harness, headers, body="One")
    assert low_balance_notices(harness, user_id) == []
    send(harness, headers, body="Two")
    assert len(low_balance_notices(harness, user_id)) == 1
    send(harness, headers, body="Three")
    assert len(low_balance_notices(harness, user_id)) == 1  # not repeated while still low
    notice = low_balance_notices(harness, user_id)[0]
    assert notice["title"] == "Demo credits are running low"
    assert "demo credits left" in notice["body"]

    # Topping up re-arms the alert; dropping again fires a new one.
    assert adjust(harness, admin, user_id, 5000).status_code == 200
    assert adjust(harness, admin, user_id, -5000).status_code == 200
    assert len(low_balance_notices(harness, user_id)) == 2


# -- history -------------------------------------------------------------------------------------


def test_history_is_paginated_newest_first_and_private(harness: Harness) -> None:
    headers, _ = ready_to_send(harness)
    other, _ = sms_user(harness)
    for index in range(3):
        send(harness, headers, body=f"Message {index}")
    pump(harness, seconds=3)

    page = harness.client.get(f"{API}/transactions?page_size=2", headers=headers).json()
    second = harness.client.get(f"{API}/transactions?page_size=2&page=2", headers=headers).json()

    assert page["pagination"]["total"] == 1 + 3 * 2  # grant + (reservation + deduction) x 3
    assert page["pagination"]["has_next"] is True
    assert len(page["data"]) == 2 and len(second["data"]) == 2
    created = [t["created_at"] for t in page["data"] + second["data"]]
    assert created == sorted(created, reverse=True)
    assert [t["entry_type"] for t in history(harness, other)] == ["grant"]
    assert history(harness, headers, ledger="live") == []


def test_credits_endpoints_need_a_signed_in_user(harness: Harness) -> None:
    for path in (API, f"{API}/transactions"):
        assert harness.client.get(path).status_code == 401, path


# -- administration ------------------------------------------------------------------------------


def _admin(harness: Harness) -> tuple[dict[str, str], str]:
    return admin_user(harness)


def test_only_administrators_can_adjust_credits(harness: Harness) -> None:
    user, user_id = sms_user(harness)
    other, other_id = sms_user(harness)

    denied = adjust(harness, user, other_id, 1000)
    anonymous = harness.client.post(
        "/api/v1/admin/credits/adjustments",
        json={"user_id": other_id, "amount_units": 1000, "reason": "No auth"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    self_service = adjust(harness, user, user_id, 1000)

    assert denied.status_code == 403 and anonymous.status_code == 401
    assert self_service.status_code == 403  # nobody can top themselves up
    assert demo(harness, other)["balance_units"] == START
    assert demo(harness, user)["balance_units"] == START
    for path in (
        f"/api/v1/admin/credits/users/{other_id}",
        f"/api/v1/admin/credits/users/{other_id}/transactions",
    ):
        assert harness.client.get(path, headers=user).status_code == 403


def test_an_adjustment_is_a_ledger_entry_with_actor_reason_audit_and_notice(
    harness: Harness,
) -> None:
    admin, admin_id = _admin(harness)
    user, user_id = sms_user(harness)

    response = adjust(harness, admin, user_id, 2500, reason="Hackathon demo top-up")

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["replayed"] is False
    assert data["balance"]["available_units"] == START + 2500
    assert data["transaction"]["entry_type"] == "adjustment"
    assert data["transaction"]["balance_after"] == START + 2500
    assert data["transaction"]["reason"] == "Hackathon demo top-up"
    row = harness.sql(
        "select actor_id, external_reference, ledger_type from public.credit_transactions "
        "where id = $1",
        uuid.UUID(data["transaction"]["id"]),
    )[0]
    assert str(row["actor_id"]) == admin_id and row["ledger_type"] == "demo"
    assert row["external_reference"].startswith("admin_adjust:")
    assert next(t["entry_type"] for t in history(harness, user)) == "adjustment"
    audit = harness.sql(
        "select action, actor_id, metadata from public.audit_logs "
        "where category = 'credit' and target_id = $1",
        user_id,
    )
    assert [a["action"] for a in audit] == ["credit.adjusted"]
    assert str(audit[0]["actor_id"]) == admin_id
    notice = harness.sql(
        "select title, body from public.notifications where user_id = $1 "
        "and notification_type = 'system' and title like '%credits were adjusted'",
        uuid.UUID(user_id),
    )
    assert len(notice) == 1 and "25.00 demo credits were added" in notice[0]["body"]
    # The admin sees the same account through the admin endpoints.
    seen = harness.client.get(f"/api/v1/admin/credits/users/{user_id}", headers=admin).json()
    assert seen["data"]["ledgers"][0]["available_units"] == START + 2500


def test_an_adjustment_is_idempotent(harness: Harness) -> None:
    admin, _ = _admin(harness)
    user, user_id = sms_user(harness)
    key = str(uuid.uuid4())

    first = adjust(harness, admin, user_id, 1000, key=key)
    again = adjust(harness, admin, user_id, 1000, key=key)
    clash = adjust(harness, admin, user_id, 2000, key=key)

    assert first.status_code == again.status_code == 200
    assert again.json()["data"]["replayed"] is True
    assert again.json()["data"]["transaction"]["id"] == first.json()["data"]["transaction"]["id"]
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "idempotency_conflict"
    assert demo(harness, user)["balance_units"] == START + 1000
    assert (
        len(
            harness.sql(
                "select 1 from public.credit_transactions where user_id = $1 "
                "and entry_type = 'adjustment'",
                uuid.UUID(user_id),
            )
        )
        == 1
    )


def test_adjustments_are_validated_and_cannot_touch_live_credit_or_overdraw(
    harness: Harness,
) -> None:
    admin, _ = _admin(harness)
    user, user_id = sms_user(harness)

    live = adjust(harness, admin, user_id, 1000, ledger="live")
    zero = adjust(harness, admin, user_id, 0)
    short_reason = adjust(harness, admin, user_id, 100, reason="x")
    huge = adjust(harness, admin, user_id, 1_000_001)
    overdraw = adjust(harness, admin, user_id, -(START + 1))
    unknown = adjust(harness, admin, str(uuid.uuid4()), 100)
    no_key = harness.client.post(
        "/api/v1/admin/credits/adjustments",
        json={"user_id": user_id, "amount_units": 100, "reason": "No key"},
        headers=admin,
    )

    assert live.status_code == 422 and live.json()["error"]["code"] == "ledger_not_adjustable"
    assert zero.status_code == short_reason.status_code == huge.status_code == 422
    assert overdraw.status_code == 422
    assert overdraw.json()["error"]["code"] == "adjustment_exceeds_balance"
    assert unknown.status_code == 404
    assert no_key.status_code == 422
    assert demo(harness, user)["balance_units"] == START
    assert [t["entry_type"] for t in history(harness, user)] == ["grant"]


def test_a_removal_cannot_dip_into_credits_held_for_queued_messages(harness: Harness) -> None:
    admin, _ = _admin(harness)
    user, user_id = ready_to_send(harness)
    cost = quote_cost(harness, user)
    send(harness, user)  # holds `cost`

    refused = adjust(harness, admin, user_id, -(START - cost + 1))

    assert refused.status_code == 422
    assert demo(harness, user)["balance_units"] == START
    assert adjust(harness, admin, user_id, -(START - cost)).status_code == 200
    ledger = demo(harness, user)
    assert (ledger["balance_units"], ledger["reserved_units"]) == (cost, cost)


def test_the_ledger_is_append_only_and_balances_always_match_it(harness: Harness) -> None:
    admin, _ = _admin(harness)
    user, user_id = ready_to_send(harness)
    adjust(harness, admin, user_id, 700)
    send(harness, user, body="A")
    send(harness, user, body="B")
    pump(harness, seconds=3)

    summed = harness.sql(
        "select sum(balance_delta) as balance, sum(reserved_delta) as reserved "
        "from public.credit_transactions where user_id = $1 and ledger_type = 'demo'",
        uuid.UUID(user_id),
    )[0]
    ledger = demo(harness, user)
    assert (summed["balance"], summed["reserved"]) == (
        ledger["balance_units"],
        ledger["reserved_units"],
    )
    for statement in (
        "update public.credit_transactions set balance_delta = 1 where user_id = $1",
        "delete from public.credit_transactions where user_id = $1",
    ):
        with pytest.raises(Exception, match=r"(?i)append|immutable|not allowed"):
            harness.sql(statement, uuid.UUID(user_id))
