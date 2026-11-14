"""Credit balances, history and administrator adjustments (Module H, simulated credits).

Nothing here overwrites a balance. An adjustment is a ledger entry with an actor, a reason and an
idempotency key, applied by the database trigger like every other entry.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.modules.audit.service import AuditLogger
from app.modules.credits import ledger
from app.modules.credits.ledger import InsufficientCreditsError, LedgerType
from app.modules.credits.repository import CreditRepository
from app.modules.credits.schemas import (
    AdjustmentOut,
    AdjustmentRequest,
    BalanceHint,
    BalanceOut,
    LedgerBalance,
    TransactionOut,
)
from app.modules.notifications.service import create_notification

UNITS = ledger.UNITS_PER_CREDIT

_DESCRIPTIONS = {
    "grant": "Starting demo credits",
    "top_up": "Credits added",
    "reservation": "Held for an SMS being sent",
    "reservation_release": "Hold released: the SMS was not accepted",
    "deduction": "SMS sent",
    "refund": "Refund: the SMS failed",
    "adjustment": "Adjusted by an administrator",
}

DEMO_NOTICE = (
    "These are simulated credits for demonstration. They are not money and cannot be bought, "
    "sold or cashed out."
)
LIVE_NOTICE = (
    "Live SMS is not metered in this version: no payment system exists, so no credits are "
    "charged or required for live messages."
)


def transaction_out(row: dict[str, Any]) -> TransactionOut:
    entry = str(row["entry_type"])
    return TransactionOut(
        id=row["id"],
        ledger=row["ledger_type"],
        entry_type=entry,
        description=_DESCRIPTIONS.get(entry, entry),
        balance_delta=int(row["balance_delta"]),
        reserved_delta=int(row["reserved_delta"]),
        credits_delta=int(row["balance_delta"]) / UNITS,
        balance_after=None if row["balance_after"] is None else int(row["balance_after"]),
        message_id=row["message_id"],
        provider=row["provider"],
        country_code=row["country_code"],
        segment_count=row["segment_count"],
        reason=row["reason"],
        created_at=row["created_at"],
    )


def _ledger_balance(kind: LedgerType, balance: int, reserved: int) -> LedgerBalance:
    available = balance - reserved
    return LedgerBalance(
        ledger=kind,
        balance_units=balance,
        reserved_units=reserved,
        available_units=available,
        available_credits=available / UNITS,
        charges_apply=kind == "demo",
    )


class CreditService:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        audit: AuditLogger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._db = database
        self._audit = audit
        self._clock = clock

    # -- reading ---------------------------------------------------------------------------

    async def _balance_for(self, user_id: UUID) -> BalanceOut:
        async with self._db.transaction() as session:
            repository = CreditRepository(session)
            balances = await repository.balances(user_id)
            threshold = await repository.threshold(user_id)
        simulated = self._settings.sms_mode == "simulation"
        active: LedgerType = "demo" if simulated else "live"
        ledgers = [_ledger_balance(kind, *balances.get(kind, (0, 0))) for kind in ("demo", "live")]
        current = next(item for item in ledgers if item.ledger == active)
        return BalanceOut(
            ledgers=ledgers,
            active_ledger=active,
            is_simulated=simulated,
            low_balance_threshold_units=threshold,
            is_low=current.charges_apply and current.available_units <= threshold,
            notice=DEMO_NOTICE if simulated else LIVE_NOTICE,
        )

    async def balance(self, user: AuthenticatedUser) -> BalanceOut:
        return await self._balance_for(user.id)

    async def history(
        self, user: AuthenticatedUser, *, ledger_type: LedgerType | None, page: int, page_size: int
    ) -> tuple[list[TransactionOut], int]:
        async with self._db.transaction() as session:
            rows, total = await CreditRepository(session).transactions(
                user.id, ledger=ledger_type, limit=page_size, offset=(page - 1) * page_size
            )
        return [transaction_out(row) for row in rows], total

    # -- administration --------------------------------------------------------------------

    async def admin_balance(self, user_id: UUID) -> BalanceOut:
        async with self._db.transaction() as session:
            if not await CreditRepository(session).user_is_active(user_id):
                raise NotFoundError("User not found.")
        return await self._balance_for(user_id)

    async def admin_history(
        self, user_id: UUID, *, page: int, page_size: int
    ) -> tuple[list[TransactionOut], int]:
        async with self._db.transaction() as session:
            repository = CreditRepository(session)
            if not await repository.user_is_active(user_id):
                raise NotFoundError("User not found.")
            rows, total = await repository.transactions(
                user_id, ledger=None, limit=page_size, offset=(page - 1) * page_size
            )
        return [transaction_out(row) for row in rows], total

    async def adjust(
        self, admin: AuthenticatedUser, request: AdjustmentRequest, key: UUID, ip: str | None
    ) -> AdjustmentOut:
        """Add or remove simulated credits. Repeating the same Idempotency-Key with the same
        content returns the original entry; with different content it is a conflict."""
        if request.ledger != "demo":
            raise UnprocessableError(
                "Only simulated (demo) credits can be adjusted. Live credit changes need the "
                "payment system.",
                code="ledger_not_adjustable",
            )
        if request.amount_units == 0:
            raise UnprocessableError("The adjustment cannot be zero.", code="zero_adjustment")
        reference = f"admin_adjust:{key}"

        async with self._db.transaction() as session:
            repository = CreditRepository(session)
            if not await repository.user_is_active(request.user_id):
                raise NotFoundError("User not found.")
            # Lock first: a concurrent request with the same key waits here, then replays.
            await ledger.lock_account(session, request.user_id, "demo")
            existing = await repository.by_reference(reference)
            if existing is not None:
                if (
                    existing["user_id"] != request.user_id
                    or int(existing["balance_delta"]) != request.amount_units
                    or existing["actor_id"] != admin.id
                ):
                    raise ConflictError(
                        "This idempotency key was already used for a different adjustment.",
                        code="idempotency_conflict",
                    )
                balances = await repository.balances(request.user_id)
                return AdjustmentOut(
                    transaction=transaction_out(existing),
                    balance=_ledger_balance("demo", *balances.get("demo", (0, 0))),
                    replayed=True,
                )

            try:
                transaction_id = await ledger.insert_entry(
                    session,
                    user_id=request.user_id,
                    ledger="demo",
                    entry_type="adjustment",
                    balance_delta=request.amount_units,
                    external_reference=reference,
                    reason=request.reason,
                    actor_id=admin.id,
                )
            except InsufficientCreditsError as exc:
                raise UnprocessableError(
                    "That would take the balance below zero or below what is held for messages "
                    "being sent.",
                    code="adjustment_exceeds_balance",
                    details=exc.details,
                ) from exc
            await self._audit.record(
                session,
                category="credit",
                action="credit.adjusted",
                actor_id=admin.id,
                actor_role=admin.role,
                target_type="user",
                target_id=str(request.user_id),
                ip=ip,
                metadata={
                    "ledger": "demo",
                    "amount_units": request.amount_units,
                    "transaction_id": str(transaction_id),
                },
            )
            direction = "added to" if request.amount_units > 0 else "removed from"
            await create_notification(
                session,
                user_id=request.user_id,
                notification_type="system",
                title="Your demo credits were adjusted",
                body=(
                    f"{abs(request.amount_units) / UNITS:.2f} demo credits were {direction} "
                    "your balance by an administrator."
                ),
                reference_type="credit_transaction",
                reference_id=transaction_id,
                dedupe_key=f"credit_adjustment:{transaction_id}",
                now=self._clock(),
            )
            await ledger.after_change(session, request.user_id, "demo")
            row = await CreditRepository(session).transaction(transaction_id)
            balances = await CreditRepository(session).balances(request.user_id)
        return AdjustmentOut(
            transaction=transaction_out(row),
            balance=_ledger_balance("demo", *balances.get("demo", (0, 0))),
            replayed=False,
        )


def balance_hint(
    *, available_units: int, cost_units: int | None, is_simulated: bool, threshold_units: int
) -> BalanceHint:
    """The credit facts shown in an SMS quote."""
    charges = is_simulated
    return BalanceHint(
        ledger="demo" if is_simulated else "live",
        is_simulated=is_simulated,
        available_units=available_units,
        available_credits=available_units / UNITS,
        sufficient=(None if cost_units is None else (not charges or cost_units <= available_units)),
        charges_apply=charges,
        is_low=charges and available_units <= threshold_units,
    )
