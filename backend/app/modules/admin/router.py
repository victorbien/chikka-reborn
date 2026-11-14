from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import AdminServiceDep, AdminUserDep, RequestMetaDep
from app.modules.admin.schemas import (
    AccountStatusFilter,
    AdminUserDetail,
    AdminUserRow,
    AiMetricsOut,
    AuditLogRow,
    DashboardOut,
    ProviderOverviewOut,
    RestrictRequest,
    RoleFilter,
    SmsMessageDetail,
    SmsMessageRow,
)
from app.schemas.common import DataResponse, PagedResponse, ok, paged

# Every route depends on AdminUserDep, which checks the role stored in the database.
router = APIRouter(prefix="/admin", tags=["admin"])

PageParam = Annotated[int, Query(ge=1, le=10_000)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


@router.get("/dashboard", summary="Platform totals from live data")
async def dashboard(admin: AdminUserDep, service: AdminServiceDep) -> DataResponse[DashboardOut]:
    return ok(await service.dashboard())


@router.get("/users", summary="Search and list accounts")
async def users(
    admin: AdminUserDep,
    service: AdminServiceDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: AccountStatusFilter | None = None,
    role: RoleFilter | None = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 30,
) -> PagedResponse[AdminUserRow]:
    items, total = await service.users(
        search=q, status=status, role=role, page=page, page_size=page_size
    )
    return paged(items, total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", summary="Account details and activity overview")
async def user_detail(
    user_id: UUID, admin: AdminUserDep, service: AdminServiceDep, meta: RequestMetaDep
) -> DataResponse[AdminUserDetail]:
    return ok(await service.user_detail(admin, user_id, meta.ip))


@router.post("/users/{user_id}/restrict", summary="Suspend an account and end its sessions")
async def restrict_user(
    user_id: UUID,
    body: RestrictRequest,
    admin: AdminUserDep,
    service: AdminServiceDep,
    meta: RequestMetaDep,
) -> DataResponse[AdminUserRow]:
    return ok(await service.restrict_user(admin, user_id, body.reason_code, meta.ip))


@router.post("/users/{user_id}/reinstate", summary="Lift a suspension")
async def reinstate_user(
    user_id: UUID, admin: AdminUserDep, service: AdminServiceDep, meta: RequestMetaDep
) -> DataResponse[AdminUserRow]:
    return ok(await service.reinstate_user(admin, user_id, meta.ip))


@router.get("/sms/messages", summary="Outbound or inbound SMS with delivery state")
async def sms_messages(
    admin: AdminUserDep,
    service: AdminServiceDep,
    direction: Literal["outbound", "inbound"] = "outbound",
    status: Annotated[str | None, Query(max_length=20)] = None,
    is_simulated: bool | None = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 30,
) -> PagedResponse[SmsMessageRow]:
    items, total = await service.sms_messages(
        direction=direction,
        status=status,
        is_simulated=is_simulated,
        page=page,
        page_size=page_size,
    )
    return paged(items, total=total, page=page, page_size=page_size)


@router.get("/sms/messages/{message_id}", summary="Delivery attempts and retry history")
async def sms_message(
    message_id: UUID, admin: AdminUserDep, service: AdminServiceDep, meta: RequestMetaDep
) -> DataResponse[SmsMessageDetail]:
    return ok(await service.sms_message(admin, message_id, meta.ip))


@router.get("/providers/overview", summary="Provider health, mode, configuration and countries")
async def provider_overview(
    admin: AdminUserDep, service: AdminServiceDep
) -> DataResponse[ProviderOverviewOut]:
    return ok(await service.provider_overview())


@router.get("/ai/metrics", summary="AI usage without conversation content")
async def ai_metrics(
    admin: AdminUserDep,
    service: AdminServiceDep,
    window_days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> DataResponse[AiMetricsOut]:
    return ok(await service.ai_metrics(window_days))


@router.get("/audit-logs", summary="Administrative and security audit trail")
async def audit_logs(
    admin: AdminUserDep,
    service: AdminServiceDep,
    category: Annotated[str | None, Query(max_length=20)] = None,
    action: Annotated[str | None, Query(max_length=60)] = None,
    outcome: Literal["success", "denied", "failure"] | None = None,
    actor_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 30,
) -> PagedResponse[AuditLogRow]:
    items, total = await service.audit_logs(
        category=category,
        action=action,
        outcome=outcome,
        actor_id=actor_id,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )
    return paged(items, total=total, page=page, page_size=page_size)
