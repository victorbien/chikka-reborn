from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query

from app.api.deps import AdminUserDep, RequestMetaDep, SmsAdminServiceDep
from app.modules.sms.admin_service import (
    ActivateRequest,
    CapabilityAdminOut,
    CapabilityUpdate,
    MonitoringOut,
    PausedRequest,
    ProviderAdminOut,
    ProviderUpdate,
    SimulateInboundOut,
    UnroutedOut,
)
from app.modules.sms.schemas import SimulateInboundRequest
from app.schemas.common import DataResponse, PagedResponse, ok, paged

router = APIRouter(prefix="/admin/sms", tags=["admin-sms"])


@router.get("/providers", summary="SMS providers (no secrets)")
async def providers(
    admin: AdminUserDep, service: SmsAdminServiceDep
) -> DataResponse[list[ProviderAdminOut]]:
    return ok(await service.providers())


@router.patch("/providers/{provider_id}", summary="Change non-secret provider settings")
async def update_provider(
    provider_id: UUID,
    body: ProviderUpdate,
    admin: AdminUserDep,
    service: SmsAdminServiceDep,
    meta: RequestMetaDep,
) -> DataResponse[list[ProviderAdminOut]]:
    return ok(await service.update_provider(admin, provider_id, body, meta.ip))


@router.post(
    "/providers/{provider_id}/activate", summary="Confirm and activate the running provider"
)
async def activate_provider(
    provider_id: UUID,
    body: ActivateRequest,
    admin: AdminUserDep,
    service: SmsAdminServiceDep,
    meta: RequestMetaDep,
) -> DataResponse[list[ProviderAdminOut]]:
    return ok(await service.activate(admin, provider_id, body, meta.ip))


@router.put("/outbound-paused", summary="Pause or resume all outbound SMS")
async def set_paused(
    body: PausedRequest, admin: AdminUserDep, service: SmsAdminServiceDep, meta: RequestMetaDep
) -> DataResponse[PausedRequest]:
    return ok(PausedRequest(paused=await service.set_paused(admin, body.paused, meta.ip)))


@router.get("/capabilities", summary="Current country capability rules")
async def capabilities(
    admin: AdminUserDep, service: SmsAdminServiceDep
) -> DataResponse[list[CapabilityAdminOut]]:
    return ok(await service.capabilities())


@router.put("/capabilities/{country_code}", summary="Publish a new version of a country's rules")
async def put_capability(
    country_code: Annotated[str, Path(pattern=r"^[A-Za-z]{2}$")],
    body: CapabilityUpdate,
    admin: AdminUserDep,
    service: SmsAdminServiceDep,
    meta: RequestMetaDep,
) -> DataResponse[CapabilityAdminOut]:
    return ok(await service.put_capability(admin, country_code, body, meta.ip))


@router.get("/monitoring", summary="Delivery health for the last 24 hours")
async def monitoring(
    admin: AdminUserDep, service: SmsAdminServiceDep
) -> DataResponse[MonitoringOut]:
    return ok(await service.monitoring())


@router.get("/inbound/unrouted", summary="Valid inbound SMS that matched no reply route")
async def unrouted(
    admin: AdminUserDep,
    service: SmsAdminServiceDep,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PagedResponse[UnroutedOut]:
    items, total = await service.unrouted(page, page_size)
    return paged(items, total=total, page=page, page_size=page_size)


@router.post("/simulate/inbound", summary="Simulate a reply (simulation mode, not production)")
async def simulate_inbound(
    body: SimulateInboundRequest,
    admin: AdminUserDep,
    service: SmsAdminServiceDep,
    meta: RequestMetaDep,
) -> DataResponse[SimulateInboundOut]:
    return ok(await service.simulate_inbound(admin, body, meta.ip))
