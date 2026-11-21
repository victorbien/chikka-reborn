from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query

from app.api.deps import ActiveUserDep, AdminUserDep, CreditServiceDep, RequestMetaDep
from app.modules.credits.schemas import (
    AdjustmentOut,
    AdjustmentRequest,
    BalanceOut,
    LedgerType,
    TransactionOut,
)
from app.schemas.common import DataResponse, PagedResponse, ok, paged

router = APIRouter(prefix="/credits", tags=["credits"])
admin_router = APIRouter(prefix="/admin/credits", tags=["admin"])


@router.get("", summary="Your simulated credit balance")
async def balance(user: ActiveUserDep, service: CreditServiceDep) -> DataResponse[BalanceOut]:
    return ok(await service.balance(user))


@router.get("/transactions", summary="Your credit history, newest first")
async def transactions(
    user: ActiveUserDep,
    service: CreditServiceDep,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    ledger: LedgerType | None = None,
) -> PagedResponse[TransactionOut]:
    items, total = await service.history(user, ledger_type=ledger, page=page, page_size=page_size)
    return paged(items, total=total, page=page, page_size=page_size)


@admin_router.get("/users/{user_id}", summary="A user's credit balance (admin)")
async def admin_balance(
    user_id: UUID, admin: AdminUserDep, service: CreditServiceDep
) -> DataResponse[BalanceOut]:
    return ok(await service.admin_balance(user_id))


@admin_router.get("/users/{user_id}/transactions", summary="A user's credit history (admin)")
async def admin_transactions(
    user_id: UUID,
    admin: AdminUserDep,
    service: CreditServiceDep,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PagedResponse[TransactionOut]:
    items, total = await service.admin_history(user_id, page=page, page_size=page_size)
    return paged(items, total=total, page=page, page_size=page_size)


@admin_router.post("/adjustments", summary="Add or remove simulated credits (admin)")
async def adjust(
    body: AdjustmentRequest,
    admin: AdminUserDep,
    service: CreditServiceDep,
    meta: RequestMetaDep,
    key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> DataResponse[AdjustmentOut]:
    return ok(await service.adjust(admin, body, key, meta.ip))
