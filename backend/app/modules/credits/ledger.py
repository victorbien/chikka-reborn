"""The credit ledger: the only code that changes a credit balance (Module H).

Balances are never written directly. Every change is an append-only `credit_transactions` row,
and a database trigger applies it to `messaging_credits`, so the balance always equals the sum of
the ledger and can never go below what is reserved.

Simulated credits only. A simulated SMS is charged to the `demo` ledger. The `live` ledger stays
untouched: real money and payments do not exist yet, so live sends are not metered and nothing
here can spend real credit (the database also rejects a live message on the demo ledger and the
reverse).

Message lifecycle (all keyed on the message, not the delivery attempt, so retries never charge
twice):

    queued        reservation          hold the estimated cost
    accepted      deduction            the provider took the message (reservation becomes spend)
    failed early  reservation_release  never accepted: the hold is returned
    failed late   refund               accepted but failed or undelivered: the spend is returned

Each of those entries exists at most once per message (unique index), and every function here
checks first, so calling it twice is harmless. Functions take the caller's session: the ledger
entry commits, or rolls back, together with the message change that caused it.
"""

import logging
import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.modules.notifications.service import create_notification

logger = logging.getLogger(__name__)

LedgerType = Literal["demo", "live"]
UNITS_PER_CREDIT = 100

_SHORTFALL = re.compile(r"available (-?\d+) units, required (\d+) units")


class InsufficientCreditsError(AppError):
    """Not enough available credits. `details` carries the amounts in units."""

    status_code = 402
    code = "insufficient_credits"


@dataclass(frozen=True)
class _Charge:
    message_id: UUID
    user_id: UUID
    units: int
    segments: int | None
    country_code: str | None
    capability_id: UUID | None


async def available_units(session: AsyncSession, user_id: UUID, ledger: LedgerType) -> int:
    """Spendable now: balance minus what is held for queued messages."""
    result = await session.execute(
        text(
            "select balance_units - reserved_units from public.messaging_credits "
            "where user_id = :user_id and ledger_type = :ledger"
        ),
        {"user_id": user_id, "ledger": ledger},
    )
    value = result.scalar_one_or_none()
    return 0 if value is None else int(value)


async def _charge_for(session: AsyncSession, message_id: UUID) -> _Charge | None:
    """What to charge for a message. None when it is not metered: not an outbound simulated
    SMS, or no cost was recorded for it (messages from before credits existed)."""
    row = (
        (
            await session.execute(
                text(
                    """
                    select m.sender_user_id, m.is_simulated, m.credit_cost_units, m.segment_count,
                           m.capability_id, c.country_code
                    from public.messages m
                    left join public.sms_country_capabilities c on c.id = m.capability_id
                    where m.id = :id and m.channel = 'sms' and m.direction = 'outbound'
                    """
                ),
                {"id": message_id},
            )
        )
        .mappings()
        .first()
    )
    if (
        row is None
        or row["sender_user_id"] is None
        or not row["is_simulated"]
        or not row["credit_cost_units"]
    ):
        return None
    return _Charge(
        message_id=message_id,
        user_id=row["sender_user_id"],
        units=int(row["credit_cost_units"]),
        segments=row["segment_count"],
        country_code=row["country_code"],
        capability_id=row["capability_id"],
    )


async def lock_account(session: AsyncSession, user_id: UUID, ledger: LedgerType) -> None:
    """Serialise ledger changes for one account. Creates the account if it is missing."""
    await session.execute(
        text(
            "insert into public.messaging_credits (user_id, ledger_type) "
            "values (:user_id, :ledger) on conflict do nothing"
        ),
        {"user_id": user_id, "ledger": ledger},
    )
    await session.execute(
        text(
            "select 1 from public.messaging_credits "
            "where user_id = :user_id and ledger_type = :ledger for update"
        ),
        {"user_id": user_id, "ledger": ledger},
    )


async def _has_entry(session: AsyncSession, message_id: UUID, entry_type: str) -> bool:
    result = await session.execute(
        text(
            "select 1 from public.credit_transactions "
            "where message_id = :message_id and entry_type = :entry_type"
        ),
        {"message_id": message_id, "entry_type": entry_type},
    )
    return result.first() is not None


async def _reserved(session: AsyncSession, message_id: UUID) -> int:
    result = await session.execute(
        text(
            "select coalesce(sum(reserved_delta), 0) from public.credit_transactions "
            "where message_id = :message_id"
        ),
        {"message_id": message_id},
    )
    return int(result.scalar_one())


async def insert_entry(
    session: AsyncSession,
    *,
    user_id: UUID,
    ledger: LedgerType,
    entry_type: str,
    balance_delta: int,
    reserved_delta: int = 0,
    message_id: UUID | None = None,
    capability_id: UUID | None = None,
    provider: str | None = None,
    country_code: str | None = None,
    segment_count: int | None = None,
    external_reference: str | None = None,
    reason: str | None = None,
    actor_id: UUID | None = None,
) -> UUID:
    """Append one ledger row. The trigger applies it and refuses an overdraw."""
    try:
        async with session.begin_nested():
            result = await session.execute(
                text(
                    """
                    insert into public.credit_transactions
                        (user_id, ledger_type, entry_type, balance_delta, reserved_delta,
                         message_id, capability_id, provider, country_code, segment_count,
                         external_reference, reason, actor_id)
                    values
                        (:user_id, :ledger, :entry_type, :balance_delta, :reserved_delta,
                         :message_id, :capability_id, :provider, :country_code, :segment_count,
                         :external_reference, :reason, :actor_id)
                    returning id
                    """
                ),
                {
                    "user_id": user_id,
                    "ledger": ledger,
                    "entry_type": entry_type,
                    "balance_delta": balance_delta,
                    "reserved_delta": reserved_delta,
                    "message_id": message_id,
                    "capability_id": capability_id,
                    "provider": provider,
                    "country_code": country_code,
                    "segment_count": segment_count,
                    "external_reference": external_reference,
                    "reason": reason,
                    "actor_id": actor_id,
                },
            )
            return UUID(str(result.scalar_one()))
    except DBAPIError as exc:
        message = str(exc.orig) if exc.orig is not None else str(exc)
        if "INSUFFICIENT_CREDITS" in message:
            shortfall = _SHORTFALL.search(message)
            details = (
                {
                    "available_units": int(shortfall.group(1)),
                    "required_units": int(shortfall.group(2)),
                }
                if shortfall
                else {}
            )
            raise InsufficientCreditsError(
                "You don't have enough credits for this.", details=details
            ) from exc
        raise


# -- message lifecycle ---------------------------------------------------------------------


async def reserve(session: AsyncSession, message_id: UUID, *, provider: str | None) -> bool:
    """Hold the estimated cost when a message is queued. Raises InsufficientCreditsError.
    Returns False when nothing was held (not metered, or already reserved)."""
    charge = await _charge_for(session, message_id)
    if charge is None:
        return False
    await lock_account(session, charge.user_id, "demo")
    if await _has_entry(session, message_id, "reservation"):
        return False
    await insert_entry(
        session,
        user_id=charge.user_id,
        ledger="demo",
        entry_type="reservation",
        balance_delta=0,
        reserved_delta=charge.units,
        message_id=message_id,
        capability_id=charge.capability_id,
        provider=provider,
        country_code=charge.country_code,
        segment_count=charge.segments,
    )
    await after_change(session, charge.user_id, "demo")
    return True


async def capture(session: AsyncSession, message_id: UUID, *, provider: str | None) -> bool:
    """Turn the hold into spend once the provider has accepted the message. Safe to repeat and
    never raises for a shortfall: the status change that triggered it must still go through."""
    charge = await _charge_for(session, message_id)
    if charge is None:
        return False
    await lock_account(session, charge.user_id, "demo")
    if await _has_entry(session, message_id, "deduction"):
        return False
    held = await _reserved(session, message_id)
    try:
        await insert_entry(
            session,
            user_id=charge.user_id,
            ledger="demo",
            entry_type="deduction",
            balance_delta=-charge.units,
            reserved_delta=-min(held, charge.units),
            message_id=message_id,
            capability_id=charge.capability_id,
            provider=provider,
            country_code=charge.country_code,
            segment_count=charge.segments,
        )
    except InsufficientCreditsError:
        logger.warning("demo credits could not be captured", extra={"message_id": str(message_id)})
        return False
    await after_change(session, charge.user_id, "demo")
    return True


async def settle_failed(session: AsyncSession, message_id: UUID, *, provider: str | None) -> bool:
    """A message permanently failed: refund what was spent, or release what was only held."""
    charge = await _charge_for(session, message_id)
    if charge is None:
        return False
    await lock_account(session, charge.user_id, "demo")
    if await _has_entry(session, message_id, "deduction"):
        if await _has_entry(session, message_id, "refund"):
            return False
        await insert_entry(
            session,
            user_id=charge.user_id,
            ledger="demo",
            entry_type="refund",
            balance_delta=charge.units,
            message_id=message_id,
            capability_id=charge.capability_id,
            provider=provider,
            country_code=charge.country_code,
            segment_count=charge.segments,
        )
    else:
        held = await _reserved(session, message_id)
        if held <= 0:
            return False
        await insert_entry(
            session,
            user_id=charge.user_id,
            ledger="demo",
            entry_type="reservation_release",
            balance_delta=0,
            reserved_delta=-held,
            message_id=message_id,
            capability_id=charge.capability_id,
            provider=provider,
            country_code=charge.country_code,
            segment_count=charge.segments,
        )
    await after_change(session, charge.user_id, "demo")
    return True


# -- low balance ---------------------------------------------------------------------------


async def after_change(session: AsyncSession, user_id: UUID, ledger: LedgerType) -> None:
    """Fire one low-balance notice when available credit drops to the user's threshold, and
    re-arm it once the balance rises above again."""
    row = (
        (
            await session.execute(
                text(
                    """
                    select mc.balance_units - mc.reserved_units as available,
                           mc.low_balance_alerted,
                           coalesce(np.low_balance_threshold_units, 500) as threshold
                    from public.messaging_credits mc
                    left join public.notification_preferences np on np.user_id = mc.user_id
                    where mc.user_id = :user_id and mc.ledger_type = :ledger
                    """
                ),
                {"user_id": user_id, "ledger": ledger},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return
    available, threshold, alerted = (
        int(row["available"]),
        int(row["threshold"]),
        row["low_balance_alerted"],
    )
    if available <= threshold and not alerted:
        await session.execute(
            text(
                "update public.messaging_credits set low_balance_alerted = true "
                "where user_id = :user_id and ledger_type = :ledger"
            ),
            {"user_id": user_id, "ledger": ledger},
        )
        crossing = (
            await session.execute(
                text(
                    "select id from public.credit_transactions where user_id = :user_id "
                    "and ledger_type = :ledger order by created_at desc, id desc limit 1"
                ),
                {"user_id": user_id, "ledger": ledger},
            )
        ).scalar_one_or_none()
        kind = "Demo credits" if ledger == "demo" else "SMS credits"
        await create_notification(
            session,
            user_id=user_id,
            notification_type="low_balance",
            title=f"{kind} are running low",
            body=f"You have {max(available, 0) / UNITS_PER_CREDIT:.2f} {kind.lower()} left.",
            dedupe_key=f"low_balance:{ledger}:{crossing}",
        )
    elif available > threshold and alerted:
        await session.execute(
            text(
                "update public.messaging_credits set low_balance_alerted = false "
                "where user_id = :user_id and ledger_type = :ledger"
            ),
            {"user_id": user_id, "ledger": ledger},
        )
