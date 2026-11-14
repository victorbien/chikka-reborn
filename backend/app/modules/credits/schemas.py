"""Request and response models for /api/v1/credits.

Units are credits x 100 (so 1.5 credits is 150 units). These are SIMULATED credits: they are not
money, cannot be bought or cashed out, and no payment exists in the application.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

LedgerType = Literal["demo", "live"]
EntryType = Literal[
    "grant",
    "top_up",
    "reservation",
    "reservation_release",
    "deduction",
    "refund",
    "adjustment",
]


class LedgerBalance(BaseModel):
    ledger: LedgerType
    balance_units: int
    reserved_units: int
    available_units: int
    available_credits: float
    # False for the live ledger: live sends are not metered until payments exist.
    charges_apply: bool


class BalanceOut(BaseModel):
    ledgers: list[LedgerBalance]
    # The ledger the current SMS mode charges: "demo" in simulation.
    active_ledger: LedgerType
    is_simulated: bool
    low_balance_threshold_units: int
    is_low: bool
    notice: str


class TransactionOut(BaseModel):
    id: UUID
    ledger: LedgerType
    entry_type: EntryType
    description: str
    balance_delta: int
    reserved_delta: int
    credits_delta: float
    balance_after: int | None
    message_id: UUID | None
    provider: str | None
    country_code: str | None
    segment_count: int | None
    reason: str | None
    created_at: datetime


class BalanceHint(BaseModel):
    """What the SMS quote says about the user's credits."""

    ledger: LedgerType
    is_simulated: bool
    available_units: int
    available_credits: float
    # None when the cost is unknown. False means the send would be refused.
    sufficient: bool | None
    # Credits are charged only when the provider accepts the message, and refunded on failure.
    charges_apply: bool
    is_low: bool


class AdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    # Positive adds credits, negative removes them.
    amount_units: Annotated[int, Field(ge=-1_000_000, le=1_000_000)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
    # Only the demo ledger can be adjusted. The live ledger is for real credit and payments.
    ledger: LedgerType = "demo"

    @field_validator("amount_units")
    @classmethod
    def _not_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("The adjustment cannot be zero")
        return value


class AdjustmentOut(BaseModel):
    transaction: TransactionOut
    balance: LedgerBalance
    # True when this was a repeat of an earlier request with the same Idempotency-Key.
    replayed: bool
