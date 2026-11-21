"""AI assistant endpoints. Every one returns a draft for the user to review: none sends."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import ActiveUserDep, AiServiceDep, RequestMetaDep
from app.modules.ai.schemas import (
    AiSettingsRequest,
    AiStatusOut,
    ComposeOut,
    ComposeRequest,
    DecisionOut,
    DecisionRequest,
    OptimiseSmsOut,
    OptimiseSmsRequest,
    RewriteOut,
    RewriteRequest,
    SuggestRepliesOut,
    SuggestRepliesRequest,
    SummariseOut,
    SummariseRequest,
    TranslateOut,
    TranslateRequest,
)
from app.schemas.common import DataResponse, ok

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", summary="Whether the assistant is available and switched on for you")
async def ai_status(user: ActiveUserDep, service: AiServiceDep) -> DataResponse[AiStatusOut]:
    return ok(await service.status(user))


@router.put("/settings", summary="Turn the AI assistant on or off for your account")
async def update_settings(
    body: AiSettingsRequest, user: ActiveUserDep, service: AiServiceDep, meta: RequestMetaDep
) -> DataResponse[AiStatusOut]:
    return ok(await service.set_enabled(user, body.enabled, meta.ip))


@router.post("/suggest-replies", summary="Draft reply suggestions (nothing is sent)")
async def suggest_replies(
    body: SuggestRepliesRequest, user: ActiveUserDep, service: AiServiceDep
) -> DataResponse[SuggestRepliesOut]:
    return ok(await service.suggest_replies(user, body))


@router.post("/translate", summary="Draft a translation (nothing is sent)")
async def translate(
    body: TranslateRequest, user: ActiveUserDep, service: AiServiceDep
) -> DataResponse[TranslateOut]:
    return ok(await service.translate(user, body))


@router.post("/rewrite", summary="Draft a rewrite or tone change (nothing is sent)")
async def rewrite(
    body: RewriteRequest, user: ActiveUserDep, service: AiServiceDep
) -> DataResponse[RewriteOut]:
    return ok(await service.rewrite(user, body))


@router.post("/optimise-sms", summary="Draft a shorter SMS with fewer segments (nothing is sent)")
async def optimise_sms(
    body: OptimiseSmsRequest, user: ActiveUserDep, service: AiServiceDep
) -> DataResponse[OptimiseSmsOut]:
    return ok(await service.optimise_sms(user, body))


@router.post("/summarise", summary="Summarise recent messages of a conversation")
async def summarise(
    body: SummariseRequest, user: ActiveUserDep, service: AiServiceDep
) -> DataResponse[SummariseOut]:
    return ok(await service.summarise(user, body))


@router.post("/compose", summary="Draft a message from a short instruction (nothing is sent)")
async def compose(
    body: ComposeRequest, user: ActiveUserDep, service: AiServiceDep
) -> DataResponse[ComposeOut]:
    return ok(await service.compose(user, body))


@router.post(
    "/assistance/{assistance_id}/decision",
    summary="Record whether you accepted, edited or dismissed a draft",
)
async def record_decision(
    assistance_id: UUID, body: DecisionRequest, user: ActiveUserDep, service: AiServiceDep
) -> DataResponse[DecisionOut]:
    return ok(await service.record_decision(user, assistance_id, body.decision))
