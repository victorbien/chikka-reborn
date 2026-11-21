from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, status

from app.api.deps import ActiveUserDep, RequestMetaDep, SmsServiceDep
from app.modules.sms.schemas import (
    ConsentOut,
    ConsentRequest,
    CountryOut,
    MarkSmsReadRequest,
    QuoteOut,
    QuoteRequest,
    RetrySmsRequest,
    SendSmsRequest,
    SmsConversationOut,
    SmsMessageDetail,
    SmsMessageOut,
    SmsMessagePage,
    SmsModeOut,
    SmsReadState,
)
from app.modules.sms.service import DEFAULT_PAGE, MAX_PAGE
from app.schemas.common import DataResponse, PagedResponse, ok, paged

router = APIRouter(prefix="/sms", tags=["sms"])

IdempotencyKey = Annotated[
    UUID, Header(alias="Idempotency-Key", description="UUID generated once per send action")
]


@router.get("/status", summary="Simulation or live, and whether you can send")
async def sms_status(user: ActiveUserDep, service: SmsServiceDep) -> DataResponse[SmsModeOut]:
    return ok(await service.status(user))


@router.get("/countries", summary="Country capabilities for the country selector")
async def countries(user: ActiveUserDep, service: SmsServiceDep) -> DataResponse[list[CountryOut]]:
    return ok(await service.countries())


@router.get("/capability", summary="Capability of one country or phone number")
async def capability(
    user: ActiveUserDep,
    service: SmsServiceDep,
    country_code: Annotated[str | None, Query(pattern=r"^[A-Za-z]{2}$")] = None,
    phone_number: Annotated[str | None, Query(max_length=32)] = None,
) -> DataResponse[CountryOut]:
    return ok(await service.capability(country_code=country_code, phone_number=phone_number))


@router.post("/quote", summary="Segments, estimated cost, consent and blockers (no side effects)")
async def quote(
    body: QuoteRequest, user: ActiveUserDep, service: SmsServiceDep
) -> DataResponse[QuoteOut]:
    return ok(await service.quote(user, body))


@router.put("/consents", summary="Record or withdraw your permission to text a recipient")
async def set_consent(
    body: ConsentRequest, user: ActiveUserDep, service: SmsServiceDep, meta: RequestMetaDep
) -> DataResponse[ConsentOut]:
    return ok(await service.set_consent(user, body, meta.ip))


@router.post(
    "/messages",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue an SMS (repeat the same Idempotency-Key to retry safely)",
    responses={200: {"description": "Already stored: the original message is returned"}},
)
async def send_sms(
    body: SendSmsRequest,
    response: Response,
    key: IdempotencyKey,
    user: ActiveUserDep,
    service: SmsServiceDep,
    meta: RequestMetaDep,
) -> DataResponse[SmsMessageOut]:
    message, created = await service.send(user, body, key, meta.ip)
    if not created:
        response.status_code = status.HTTP_200_OK
    return ok(message)


@router.post(
    "/messages/{message_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a failed message again as a new message",
)
async def retry_sms(
    message_id: UUID,
    body: RetrySmsRequest,
    response: Response,
    key: IdempotencyKey,
    user: ActiveUserDep,
    service: SmsServiceDep,
    meta: RequestMetaDep,
) -> DataResponse[SmsMessageOut]:
    message, created = await service.retry(user, message_id, key, meta.ip)
    if not created:
        response.status_code = status.HTTP_200_OK
    return ok(message)


@router.get("/messages/{message_id}", summary="One SMS with its delivery history")
async def get_sms(
    message_id: UUID, user: ActiveUserDep, service: SmsServiceDep
) -> DataResponse[SmsMessageDetail]:
    return ok(await service.get_message(user, message_id))


@router.get("/conversations", summary="Your SMS conversations, newest activity first")
async def list_conversations(
    user: ActiveUserDep,
    service: SmsServiceDep,
    archived: bool = False,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> PagedResponse[SmsConversationOut]:
    items, total = await service.list_conversations(
        user, archived=archived, page=page, page_size=page_size
    )
    return paged(items, total=total, page=page, page_size=page_size)


@router.get("/conversations/{conversation_id}/messages", summary="SMS history, oldest first")
async def list_messages(
    conversation_id: UUID,
    user: ActiveUserDep,
    service: SmsServiceDep,
    before_seq: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = DEFAULT_PAGE,
) -> DataResponse[SmsMessagePage]:
    return ok(
        await service.list_messages(user, conversation_id, before_seq=before_seq, limit=limit)
    )


@router.post("/conversations/{conversation_id}/read", summary="Mark replies as read")
async def mark_read(
    conversation_id: UUID,
    body: MarkSmsReadRequest,
    user: ActiveUserDep,
    service: SmsServiceDep,
) -> DataResponse[SmsReadState]:
    return ok(await service.mark_read(user, conversation_id, body.up_to_seq))
