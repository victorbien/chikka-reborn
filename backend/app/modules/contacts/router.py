from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Query, Response, status

from app.api.deps import ActiveUserDep, ContactServiceDep
from app.modules.contacts.schemas import (
    AcceptRequest,
    BlockCreate,
    BlockItem,
    ContactDetail,
    ContactFilter,
    ContactRequestCreate,
    ContactRequestItem,
    ContactRequestSent,
    ContactSummary,
    ContactUpdate,
    GroupCreate,
    GroupMembersRequest,
    GroupResponse,
    GroupUpdate,
    RecentContact,
    RecentConversation,
    RejectRequest,
    SearchResponse,
)
from app.schemas.common import DataResponse, PagedResponse, ok, paged

router = APIRouter(prefix="/contacts", tags=["contacts"])

Page = Annotated[int, Query(ge=1, le=10_000)]
PageSize = Annotated[int, Query(ge=1, le=100)]


# -- buddy list and discovery ----------------------------------------------------------------


@router.get("", summary="Your buddy list")
async def list_contacts(
    user: ActiveUserDep,
    service: ContactServiceDep,
    contact_filter: Annotated[ContactFilter, Query(alias="filter")] = "all",
    group_id: UUID | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> PagedResponse[ContactSummary]:
    items, total = await service.list_contacts(
        user, contact_filter=contact_filter, group_id=group_id, page=page, page_size=page_size
    )
    return paged(items, total=total, page=page, page_size=page_size)


@router.get("/search", summary="Search your contacts and find people by exact username")
async def search(
    user: ActiveUserDep,
    service: ContactServiceDep,
    q: Annotated[str, Query(max_length=254)],
) -> DataResponse[SearchResponse]:
    return ok(await service.search(user, q))


@router.get("/recent", summary="Contacts you talked to most recently")
async def recent_contacts(
    user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[list[RecentContact]]:
    return ok(await service.recent_contacts(user))


@router.delete(
    "/recent", status_code=status.HTTP_204_NO_CONTENT, summary="Clear the recent contacts list"
)
async def clear_recent(user: ActiveUserDep, service: ContactServiceDep) -> Response:
    await service.clear_recent(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/recent-conversations", summary="Your latest conversations")
async def recent_conversations(
    user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[list[RecentConversation]]:
    return ok(await service.recent_conversations(user))


# -- requests --------------------------------------------------------------------------------


@router.post("/requests", summary="Ask someone to be your contact")
async def send_request(
    body: ContactRequestCreate, user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[ContactRequestSent]:
    return ok(await service.send_request(user, body))


@router.get("/requests", summary="Pending contact requests")
async def list_requests(
    user: ActiveUserDep,
    service: ContactServiceDep,
    direction: Annotated[str, Query(pattern="^(incoming|outgoing)$")] = "incoming",
    page: Page = 1,
    page_size: PageSize = 50,
) -> PagedResponse[ContactRequestItem]:
    items, total = await service.list_requests(
        user, incoming=direction == "incoming", page=page, page_size=page_size
    )
    return paged(items, total=total, page=page, page_size=page_size)


@router.post("/requests/{request_id}/accept", summary="Accept a request")
async def accept_request(
    request_id: UUID,
    user: ActiveUserDep,
    service: ContactServiceDep,
    body: Annotated[AcceptRequest | None, Body()] = None,
) -> DataResponse[ContactDetail]:
    group_id = body.group_id if body is not None else None
    return ok(await service.accept_request(user, request_id, group_id))


@router.post(
    "/requests/{request_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reject a request (the sender is not told)",
)
async def reject_request(
    request_id: UUID,
    user: ActiveUserDep,
    service: ContactServiceDep,
    body: Annotated[RejectRequest | None, Body()] = None,
) -> Response:
    await service.reject_request(user, request_id, block=bool(body and body.block))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/requests/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a request you sent",
)
async def cancel_request(
    request_id: UUID, user: ActiveUserDep, service: ContactServiceDep
) -> Response:
    await service.cancel_request(user, request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- groups ----------------------------------------------------------------------------------


@router.get("/groups", summary="Your contact groups")
async def list_groups(
    user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[list[GroupResponse]]:
    return ok(await service.list_groups(user))


@router.post("/groups", status_code=status.HTTP_201_CREATED, summary="Create a group")
async def create_group(
    body: GroupCreate, user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[GroupResponse]:
    return ok(await service.create_group(user, body))


@router.patch("/groups/{group_id}", summary="Rename or recolour a group")
async def update_group(
    group_id: UUID, body: GroupUpdate, user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[GroupResponse]:
    return ok(await service.update_group(user, group_id, body))


@router.delete(
    "/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a group (contacts are kept)",
)
async def delete_group(group_id: UUID, user: ActiveUserDep, service: ContactServiceDep) -> Response:
    await service.delete_group(user, group_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/groups/{group_id}/members", summary="Add contacts to a group")
async def add_group_members(
    group_id: UUID, body: GroupMembersRequest, user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[GroupResponse]:
    return ok(await service.add_group_members(user, group_id, body.contact_ids))


@router.delete(
    "/groups/{group_id}/members/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a contact from a group",
)
async def remove_group_member(
    group_id: UUID, contact_id: UUID, user: ActiveUserDep, service: ContactServiceDep
) -> Response:
    await service.remove_group_member(user, group_id, contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- blocks ----------------------------------------------------------------------------------


@router.get("/blocks", summary="People you blocked")
async def list_blocks(
    user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[list[BlockItem]]:
    return ok(await service.list_blocks(user))


@router.post("/blocks", status_code=status.HTTP_201_CREATED, summary="Block someone")
async def block_user(
    body: BlockCreate, user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[BlockItem]:
    return ok(await service.block_user(user, body.user_id))


@router.delete(
    "/blocks/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Unblock someone"
)
async def unblock_user(user_id: UUID, user: ActiveUserDep, service: ContactServiceDep) -> Response:
    await service.unblock_user(user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- single contact (registered last so fixed paths above win) -------------------------------


@router.get("/{contact_id}", summary="A contact's profile")
async def get_contact(
    contact_id: UUID, user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[ContactDetail]:
    return ok(await service.get_contact(user, contact_id))


@router.patch("/{contact_id}", summary="Favourite a contact or set a nickname")
async def update_contact(
    contact_id: UUID, body: ContactUpdate, user: ActiveUserDep, service: ContactServiceDep
) -> DataResponse[ContactDetail]:
    return ok(await service.update_contact(user, contact_id, body))


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a contact")
async def remove_contact(
    contact_id: UUID, user: ActiveUserDep, service: ContactServiceDep
) -> Response:
    await service.remove_contact(user, contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
