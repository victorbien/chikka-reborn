from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query

from app.api.deps import ActiveUserDep, AdminUserDep, NotificationServiceDep, RequestMetaDep
from app.modules.notifications.preferences import NotificationType
from app.modules.notifications.schemas import (
    AnnouncementOut,
    AnnouncementRequest,
    MarkAllReadOut,
    NotificationOut,
    PreferencesOut,
    PreferencesUpdate,
    UnreadCountOut,
)
from app.schemas.common import DataResponse, PagedResponse, ok, paged

router = APIRouter(prefix="/notifications", tags=["notifications"])
admin_router = APIRouter(prefix="/admin/notifications", tags=["admin"])


@router.get("", summary="Your notifications, newest first")
async def list_notifications(
    user: ActiveUserDep,
    service: NotificationServiceDep,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    unread_only: bool = False,
    type: NotificationType | None = None,
) -> PagedResponse[NotificationOut]:
    items, total = await service.feed(
        user, unread_only=unread_only, kind=type, page=page, page_size=page_size
    )
    return paged(items, total=total, page=page, page_size=page_size)


@router.get("/unread-count", summary="How many notifications you have not read")
async def unread_count(
    user: ActiveUserDep, service: NotificationServiceDep
) -> DataResponse[UnreadCountOut]:
    return ok(await service.unread_count(user))


@router.post("/read-all", summary="Mark every notification as read")
async def read_all(
    user: ActiveUserDep,
    service: NotificationServiceDep,
    type: NotificationType | None = None,
) -> DataResponse[MarkAllReadOut]:
    return ok(await service.mark_all_read(user, type))


@router.get("/preferences", summary="Your notification settings")
async def get_preferences(
    user: ActiveUserDep, service: NotificationServiceDep
) -> DataResponse[PreferencesOut]:
    return ok(await service.preferences(user))


@router.put("/preferences", summary="Change your notification settings")
async def update_preferences(
    body: PreferencesUpdate, user: ActiveUserDep, service: NotificationServiceDep
) -> DataResponse[PreferencesOut]:
    return ok(await service.update_preferences(user, body))


@router.post("/{notification_id}/read", summary="Mark one notification as read")
async def read_one(
    notification_id: UUID, user: ActiveUserDep, service: NotificationServiceDep
) -> DataResponse[NotificationOut]:
    return ok(await service.mark_read(user, notification_id))


@router.post("/{notification_id}/dismiss", summary="Remove a notification from your list")
async def dismiss(
    notification_id: UUID, user: ActiveUserDep, service: NotificationServiceDep
) -> DataResponse[UnreadCountOut]:
    return ok(await service.dismiss(user, notification_id))


@admin_router.post("", summary="Send a system notice to one user or everyone (admin)")
async def announce(
    body: AnnouncementRequest,
    admin: AdminUserDep,
    service: NotificationServiceDep,
    meta: RequestMetaDep,
    key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> DataResponse[AnnouncementOut]:
    return ok(await service.announce(admin, body, key, meta.ip))
