"""Reads of balances and the ledger. Writes go through ledger.py."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_TX_COLUMNS = """
    id, ledger_type, entry_type, balance_delta, reserved_delta, balance_after, message_id,
    provider, country_code, segment_count, reason, created_at
"""


class CreditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def balances(self, user_id: UUID) -> dict[str, tuple[int, int]]:
        rows = await self._session.execute(
            text(
                "select ledger_type, balance_units, reserved_units "
                "from public.messaging_credits where user_id = :user_id"
            ),
            {"user_id": user_id},
        )
        return {r[0]: (int(r[1]), int(r[2])) for r in rows}

    async def threshold(self, user_id: UUID) -> int:
        result = await self._session.execute(
            text(
                "select low_balance_threshold_units from public.notification_preferences "
                "where user_id = :user_id"
            ),
            {"user_id": user_id},
        )
        value = result.scalar_one_or_none()
        return 500 if value is None else int(value)

    async def transactions(
        self, user_id: UUID, *, ledger: str | None, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        params: dict[str, Any] = {"user_id": user_id, "ledger": ledger}
        where = "user_id = :user_id and (cast(:ledger as text) is null or ledger_type = :ledger)"
        total = (
            await self._session.execute(
                text(f"select count(*) from public.credit_transactions where {where}"),  # noqa: S608
                params,
            )
        ).scalar_one()
        rows = (
            (
                await self._session.execute(
                    text(
                        f"select {_TX_COLUMNS} from public.credit_transactions "  # noqa: S608
                        f"where {where} order by created_at desc, id desc "
                        "limit :limit offset :offset"
                    ),
                    {**params, "limit": limit, "offset": offset},
                )
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows], int(total)

    async def by_reference(self, reference: str) -> dict[str, Any] | None:
        row = (
            (
                await self._session.execute(
                    text(
                        f"select {_TX_COLUMNS}, user_id, actor_id from "  # noqa: S608
                        "public.credit_transactions where external_reference = :reference"
                    ),
                    {"reference": reference},
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    async def transaction(self, transaction_id: UUID) -> dict[str, Any]:
        row = (
            (
                await self._session.execute(
                    text(
                        f"select {_TX_COLUMNS} from public.credit_transactions "  # noqa: S608
                        "where id = :id"
                    ),
                    {"id": transaction_id},
                )
            )
            .mappings()
            .one()
        )
        return dict(row)

    async def user_is_active(self, user_id: UUID) -> bool:
        result = await self._session.execute(
            text("select 1 from public.profiles where id = :id and status = 'active'"),
            {"id": user_id},
        )
        return result.first() is not None
