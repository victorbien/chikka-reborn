from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.api.deps import ActiveUserDep, ChatServiceDep
from app.modules.chat.attachments import MAX_ATTACHMENT_BYTES
from app.modules.chat.schemas import (
    AttachmentOut,
    ConversationSummary,
    ConversationUpdate,
    MarkReadRequest,
    MessageOut,
    MessagePage,
    OpenConversationRequest,
    ReadState,
    SendMessageRequest,
    UnreadTotals,
)
from app.modules.chat.service import DEFAULT_PAGE, MAX_PAGE
from app.schemas.common import DataResponse, PagedResponse, ok, paged

router = APIRouter(prefix="/conversations", tags=["messaging"])

Seq = Annotated[int, Query(ge=0)]


@router.get("", summary="Your conversations, newest activity first")
async def list_conversations(
    user: ActiveUserDep,
    service: ChatServiceDep,
    archived: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PagedResponse[ConversationSummary]:
    items, total = await service.list_conversations(
        user, archived=archived, query=q, page=page, page_size=page_size
    )
    return paged(items, total=total, page=page, page_size=page_size)


@router.post("", summary="Open (or create) the conversation with a contact")
async def open_conversation(
    body: OpenConversationRequest, user: ActiveUserDep, service: ChatServiceDep
) -> DataResponse[ConversationSummary]:
    return ok(await service.open_conversation(user, body.user_id))


@router.get("/unread", summary="Unread totals for the navigation badge")
async def unread_totals(user: ActiveUserDep, service: ChatServiceDep) -> DataResponse[UnreadTotals]:
    return ok(await service.unread_totals(user))


@router.get("/{conversation_id}", summary="One conversation")
async def get_conversation(
    conversation_id: UUID, user: ActiveUserDep, service: ChatServiceDep
) -> DataResponse[ConversationSummary]:
    return ok(await service.get_conversation(user, conversation_id))


@router.patch("/{conversation_id}", summary="Archive or unarchive (only for you)")
async def update_conversation(
    conversation_id: UUID, body: ConversationUpdate, user: ActiveUserDep, service: ChatServiceDep
) -> DataResponse[ConversationSummary]:
    return ok(await service.set_archived(user, conversation_id, body.is_archived))


@router.get("/{conversation_id}/messages", summary="Message history, oldest first within a page")
async def list_messages(
    conversation_id: UUID,
    user: ActiveUserDep,
    service: ChatServiceDep,
    before_seq: Seq | None = None,
    after_seq: Seq | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = DEFAULT_PAGE,
) -> DataResponse[MessagePage]:
    return ok(
        await service.list_messages(
            user, conversation_id, before_seq=before_seq, after_seq=after_seq, limit=limit
        )
    )


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Send a message (repeat the same client_message_id to retry safely)",
    responses={200: {"description": "Already stored: the original message is returned"}},
)
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    response: Response,
    user: ActiveUserDep,
    service: ChatServiceDep,
) -> DataResponse[MessageOut]:
    message, created = await service.send_message(user, conversation_id, body)
    if not created:
        response.status_code = status.HTTP_200_OK
    return ok(message)


@router.post("/{conversation_id}/read", summary="Mark messages up to a sequence number as read")
async def mark_read(
    conversation_id: UUID, body: MarkReadRequest, user: ActiveUserDep, service: ChatServiceDep
) -> DataResponse[ReadState]:
    return ok(await service.mark_read(user, conversation_id, body.up_to_seq))


@router.post(
    "/{conversation_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file to attach (JPEG, PNG, WebP, GIF or PDF, up to 10 MB)",
)
async def upload_attachment(
    conversation_id: UUID,
    user: ActiveUserDep,
    service: ChatServiceDep,
    file: Annotated[UploadFile, File(description="The file")],
) -> DataResponse[AttachmentOut]:
    # Read at most one byte past the limit so oversized files never sit fully in memory.
    data = await file.read(MAX_ATTACHMENT_BYTES + 1)
    name = file.filename
    await file.close()
    return ok(await service.upload_attachment(user, conversation_id, name, data))
