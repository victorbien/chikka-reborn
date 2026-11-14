"""The AI assistant: drafts only.

Nothing in this module sends a message. Every method returns a draft (or nothing) for the user
to review, and the only follow-up the backend accepts is the user's decision about it.

Privacy: conversation context is limited to the newest few messages, masked (emails, long
numbers) and labelled me/them. Prompts, drafts and conversation text are never logged and never
stored: ai_assistance_logs keeps metadata and a hash of the output.
"""

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import (
    BadGatewayError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    UnprocessableError,
)
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.integrations.ai.base import (
    AiCompletion,
    AiFeature,
    AiProvider,
    AiProviderError,
    AiRequest,
)
from app.modules.ai import outputs, prompts
from app.modules.ai.languages import LANGUAGES
from app.modules.ai.outputs import InvalidOutputError, SmsOptimisation
from app.modules.ai.redaction import minimise_context, minimise_texts
from app.modules.ai.repository import AiRepository, Gate, LogEntry
from app.modules.ai.schemas import (
    AiStatusOut,
    ComposeOut,
    ComposeRequest,
    Decision,
    DecisionOut,
    LanguageOut,
    OptimiseSmsOut,
    OptimiseSmsRequest,
    RewriteOut,
    RewriteRequest,
    SegmentCount,
    SuggestRepliesOut,
    SuggestRepliesRequest,
    SummariseOut,
    SummariseRequest,
    TranslateOut,
    TranslateRequest,
)
from app.modules.ai.settings import MAX_TEXT_CHARS
from app.modules.audit.service import AuditLogger
from app.modules.chat.context import ConversationAiContext
from app.modules.rate_limits import service as limits
from app.modules.sms.segments import SegmentInfo, analyse

logger = logging.getLogger(__name__)

_NO_DRAFT = "Couldn't generate a suggestion. Try again, or write the message yourself."
_DECLINED = "The assistant can't help with this message. You can still write it yourself."
_UNAVAILABLE = "The AI assistant is unavailable right now. You can keep writing your message."

_OUTCOME_FOR_FAILURE = {
    "timeout": "timeout",
    "throttled": "throttled",
    "unavailable": "unavailable",
    "blocked": "blocked",
    "configuration": "unavailable",
}


class ChatContextSource(Protocol):
    async def ai_context(
        self, user: AuthenticatedUser, conversation_id: UUID, limit: int
    ) -> ConversationAiContext: ...


class Limiter(Protocol):
    async def hit(self, limit: limits.Limit, subject: str) -> None: ...


@dataclass(frozen=True)
class _Result[T]:
    value: T | None
    assistance_id: UUID | None
    model_id: str
    latency_ms: int
    message: str | None


class AiService:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        provider: AiProvider,
        limiter: Limiter,
        chat: ChatContextSource,
        audit: AuditLogger,
        repository_factory: Callable[[AsyncSession], AiRepository] = AiRepository,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._db = database
        self._provider = provider
        self._limiter = limiter
        self._chat = chat
        self._audit = audit
        self._repository = repository_factory
        self._monotonic = monotonic

    # -- settings and consent ----------------------------------------------------------------

    async def status(self, user: AuthenticatedUser) -> AiStatusOut:
        gate = await self._gate(user)
        return AiStatusOut(
            available=gate.platform_enabled,
            enabled=gate.user_enabled,
            simulated=self._provider.is_simulated,
            model_id=self._provider.model_id,
            languages=[LanguageOut(code=code, name=name) for code, name in LANGUAGES.items()],
            max_text_chars=MAX_TEXT_CHARS,
        )

    async def set_enabled(
        self, user: AuthenticatedUser, enabled: bool, ip: str | None
    ) -> AiStatusOut:
        await self._limiter.hit(limits.PROFILE_WRITE_PER_USER, str(user.id))
        async with self._db.transaction() as session:
            await self._repository(session).set_user_enabled(user.id, enabled)
            await self._audit.record(
                session,
                category="consent",
                action="ai.enabled" if enabled else "ai.disabled",
                actor_id=user.id,
                actor_role=user.role,
                ip=ip,
            )
        return await self.status(user)

    async def record_decision(
        self, user: AuthenticatedUser, assistance_id: UUID, decision: Decision
    ) -> DecisionOut:
        async with self._db.transaction() as session:
            found = await self._repository(session).set_decision(assistance_id, user.id, decision)
        if not found:
            raise NotFoundError("That suggestion was not found.")
        return DecisionOut(assistance_id=assistance_id, decision=decision)

    # -- features ----------------------------------------------------------------------------

    async def suggest_replies(
        self, user: AuthenticatedUser, body: SuggestRepliesRequest
    ) -> SuggestRepliesOut:
        await self._admit(user)
        lines = await self._conversation_lines(
            user, body.conversation_id, body.context_message_count
        )
        request = prompts.build_request(
            "suggest_replies",
            {"count": body.count, "conversation": lines},
            max_tokens=self._settings.ai_max_output_tokens,
            temperature=0.7,
        )
        result = await self._complete(
            user,
            request,
            conversation_id=body.conversation_id,
            parse=lambda raw: outputs.parse_suggestions(raw, count=body.count),
        )
        return SuggestRepliesOut(**self._meta(result), suggestions=result.value or [])

    async def translate(self, user: AuthenticatedUser, body: TranslateRequest) -> TranslateOut:
        await self._admit(user)
        source = LANGUAGES[body.source_language] if body.source_language else "auto-detect"
        request = prompts.build_request(
            "translate",
            {
                "text": body.text,
                "source_language": source,
                "target_language": LANGUAGES[body.target_language],
            },
            max_tokens=self._settings.ai_max_output_tokens,
            temperature=0.1,
        )
        result = await self._complete(
            user, request, language=body.target_language, parse=outputs.parse_text
        )
        return TranslateOut(
            **self._meta(result),
            original_text=body.text,
            translated_text=result.value,
            source_language=body.source_language,
            target_language=body.target_language,
        )

    async def rewrite(self, user: AuthenticatedUser, body: RewriteRequest) -> RewriteOut:
        await self._admit(user)
        if body.instruction == "adjust_tone":
            feature: AiFeature = "tone_adjust"
            payload: dict[str, Any] = {"text": body.text, "tone": body.tone}
        else:
            feature = "rewrite"
            payload = {
                "text": body.text,
                "instruction": prompts.REWRITE_INSTRUCTIONS[body.instruction],
            }
        request = prompts.build_request(
            feature, payload, max_tokens=self._settings.ai_max_output_tokens
        )
        result = await self._complete(user, request, parse=outputs.parse_text)
        return RewriteOut(
            **self._meta(result),
            original_text=body.text,
            rewritten_text=result.value,
            instruction=body.instruction,
        )

    async def summarise(self, user: AuthenticatedUser, body: SummariseRequest) -> SummariseOut:
        await self._admit(user)
        lines = await self._conversation_lines(user, body.conversation_id, body.message_count)
        guide, limit = prompts.SUMMARY_LENGTH_GUIDE[body.length]
        request = prompts.build_request(
            "summarise",
            {"messages": lines, "length_guide": guide},
            max_tokens=self._settings.ai_max_output_tokens,
        )
        result = await self._complete(
            user,
            request,
            conversation_id=body.conversation_id,
            parse=lambda raw: outputs.parse_summary(raw, limit=limit),
        )
        return SummariseOut(
            **self._meta(result), summary=result.value, messages_summarised=len(lines)
        )

    async def compose(self, user: AuthenticatedUser, body: ComposeRequest) -> ComposeOut:
        await self._admit(user)
        request = prompts.build_request(
            "compose",
            {
                "instruction": body.prompt,
                "context": minimise_texts(body.context),
                "language": LANGUAGES[body.language] if body.language else None,
                "max_characters": body.max_length,
            },
            max_tokens=self._settings.ai_max_output_tokens,
            temperature=0.5,
        )
        result = await self._complete(
            user,
            request,
            language=body.language,
            parse=lambda raw: outputs.parse_composed(raw, max_characters=body.max_length),
        )
        text = result.value
        return ComposeOut(
            **self._meta(result),
            composed_text=text,
            character_count=len(text or ""),
            segments=_segment_count(analyse(text)) if text else None,
        )

    async def optimise_sms(
        self, user: AuthenticatedUser, body: OptimiseSmsRequest
    ) -> OptimiseSmsOut:
        original = analyse(body.text)
        if original.segments <= body.max_segments:
            # Nothing to gain, so the model is not called and nothing is logged.
            return OptimiseSmsOut(
                assistance_id=None,
                model_id=self._provider.model_id,
                latency_ms=0,
                simulated=self._provider.is_simulated,
                message=f"This message already fits in {body.max_segments} segment(s).",
                original_text=body.text,
                optimised_text=None,
                original=_segment_count(original),
                optimised=None,
                max_segments=body.max_segments,
                within_target=True,
                meaning_preserved=None,
            )

        await self._admit(user)
        request = prompts.build_request(
            "optimise_sms",
            {"text": body.text, "max_units": _max_units(original, body.max_segments)},
            max_tokens=self._settings.ai_max_output_tokens,
            temperature=0.2,
        )
        result = await self._complete(
            user,
            request,
            parse=outputs.parse_sms_optimisation,
            meaning=lambda value: value.meaning_preserved,
        )
        return self._optimisation_out(result, body, original)

    # -- internals ---------------------------------------------------------------------------

    def _optimisation_out(
        self, result: _Result[SmsOptimisation], body: OptimiseSmsRequest, original: SegmentInfo
    ) -> OptimiseSmsOut:
        draft = result.value
        optimised = analyse(draft.text) if draft is not None and draft.text else None
        message = result.message
        text = draft.text if draft is not None else None
        if draft is not None and not draft.meaning_preserved:
            message = (
                f"This message can't be shortened to {body.max_segments} segment(s) without "
                "losing important information. Consider splitting it into two messages."
            )
        elif optimised is not None and optimised.segments >= original.segments:
            # A rewrite that saves no segment is not worth the risk of changing the meaning.
            text, optimised = None, None
            message = "No shorter version with fewer segments was found."
        return OptimiseSmsOut(
            **self._meta(result, message=message),
            original_text=body.text,
            optimised_text=text,
            original=_segment_count(original),
            optimised=_segment_count(optimised) if optimised else None,
            max_segments=body.max_segments,
            within_target=optimised is not None and optimised.segments <= body.max_segments,
            meaning_preserved=draft.meaning_preserved if draft is not None else None,
        )

    def _meta(self, result: _Result[Any], *, message: str | None = None) -> dict[str, Any]:
        return {
            "assistance_id": result.assistance_id,
            "model_id": result.model_id,
            "latency_ms": result.latency_ms,
            "simulated": self._provider.is_simulated,
            "message": message if message is not None else result.message,
        }

    async def _gate(self, user: AuthenticatedUser) -> Gate:
        async with self._db.transaction() as session:
            return await self._repository(session).gate(user.id)

    async def _admit(self, user: AuthenticatedUser) -> None:
        """Kill switch, the user's opt-in, then the hourly limit. All fail closed."""
        gate = await self._gate(user)
        if not gate.platform_enabled:
            raise ServiceUnavailableError(
                "AI features are switched off right now.", code="ai_disabled_by_admin"
            )
        if not gate.user_enabled:
            raise PermissionDeniedError(
                "Turn on the AI assistant in your settings to use it.", code="ai_not_enabled"
            )
        await self._limiter.hit(
            limits.Limit(
                "ai.request.user",
                gate.hourly_limit,
                3600,
                message="AI features are paused for now because you have used your hourly limit.",
            ),
            str(user.id),
        )

    async def _conversation_lines(
        self, user: AuthenticatedUser, conversation_id: UUID, limit: int
    ) -> list[dict[str, str]]:
        context = await self._chat.ai_context(user, conversation_id, limit)
        if not context.ai_enabled:
            raise PermissionDeniedError(
                "The AI assistant is turned off for this conversation.",
                code="ai_disabled_for_conversation",
            )
        lines = minimise_context(context.lines, limit)
        if not lines:
            raise UnprocessableError("There are no messages to work with yet.", code="no_context")
        return lines

    async def _call(self, request: AiRequest) -> AiCompletion:
        """One attempt, plus one retry for a transient failure (timeout, unavailable)."""
        try:
            return await self._provider.complete(request)
        except AiProviderError as exc:
            if not exc.is_transient:
                raise
        return await self._provider.complete(request)

    async def _complete[T](
        self,
        user: AuthenticatedUser,
        request: AiRequest,
        *,
        parse: Callable[[str], T],
        conversation_id: UUID | None = None,
        language: str | None = None,
        meaning: Callable[[T], bool | None] | None = None,
    ) -> _Result[T]:
        started = self._monotonic()

        def elapsed_ms() -> int:
            return max(0, int((self._monotonic() - started) * 1000))

        model_id = self._provider.model_id
        try:
            completion = await self._call(request)
        except AiProviderError as exc:
            latency = elapsed_ms()
            await self._log(
                user, request, conversation_id, language, model_id, latency,
                outcome=_OUTCOME_FOR_FAILURE[exc.failure], error_code=exc.failure,
            )  # fmt: skip
            if exc.failure == "blocked":
                return _Result(None, None, model_id, latency, _DECLINED)
            raise BadGatewayError(
                _UNAVAILABLE, code="ai_unavailable", details={"reason": exc.failure}
            ) from exc

        latency = elapsed_ms()
        model_id = completion.model_id
        try:
            value = parse(completion.text)
        except InvalidOutputError:
            assistance_id = await self._log(
                user, request, conversation_id, language, model_id, latency,
                outcome="invalid_output", error_code="invalid_output",
                tokens=(completion.input_tokens, completion.output_tokens),
            )  # fmt: skip
            return _Result(None, assistance_id, model_id, latency, _NO_DRAFT)

        assistance_id = await self._log(
            user, request, conversation_id, language, model_id, latency,
            outcome="success", output=completion.text,
            meaning=meaning(value) if meaning else None,
            tokens=(completion.input_tokens, completion.output_tokens),
        )  # fmt: skip
        return _Result(value, assistance_id, model_id, latency, None)

    async def _log(
        self,
        user: AuthenticatedUser,
        request: AiRequest,
        conversation_id: UUID | None,
        language: str | None,
        model_id: str,
        latency_ms: int,
        *,
        outcome: str,
        error_code: str | None = None,
        output: str | None = None,
        meaning: bool | None = None,
        tokens: tuple[int | None, int | None] = (None, None),
    ) -> UUID | None:
        """Metadata only. A failed audit write never changes what the user sees."""
        entry = LogEntry(
            user_id=user.id,
            conversation_id=conversation_id,
            feature=request.feature,
            model_id=model_id,
            prompt_version=prompts.PROMPT_VERSION,
            language=language,
            outcome=outcome,
            meaning_preserved=meaning,
            input_tokens=tokens[0],
            output_tokens=tokens[1],
            latency_ms=latency_ms,
            error_code=error_code,
            output_hash=hashlib.sha256(output.encode()).hexdigest() if output else None,
        )
        logger.info(
            "ai request",
            extra={
                "feature": request.feature,
                "outcome": outcome,
                "model_id": model_id,
                "latency_ms": latency_ms,
                "input_tokens": tokens[0],
                "output_tokens": tokens[1],
            },
        )
        try:
            async with self._db.transaction() as session:
                return await self._repository(session).insert_log(entry)
        except Exception as exc:
            logger.error("ai log write failed", extra={"error_type": type(exc).__name__})
            return None


def _segment_count(info: SegmentInfo) -> SegmentCount:
    return SegmentCount(
        characters=info.characters, units=info.units, segments=info.segments, encoding=info.encoding
    )


def _max_units(original: SegmentInfo, max_segments: int) -> int:
    """Unit budget for the target segment count, in the original's encoding."""
    if original.encoding == "gsm7":
        return 160 if max_segments == 1 else 153 * max_segments
    return 70 if max_segments == 1 else 67 * max_segments
