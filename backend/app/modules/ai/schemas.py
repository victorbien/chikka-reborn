"""Request and response models for /api/v1/ai.

Every response is a draft. No model here carries a "send" field, and no endpoint sends.
"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.ai.languages import LANGUAGES
from app.modules.ai.settings import (
    MAX_CONTEXT_LINE_CHARS,
    MAX_CONTEXT_MESSAGES,
    MAX_PROMPT_CHARS,
    MAX_SUMMARY_MESSAGES,
    MAX_TEXT_CHARS,
)
from app.modules.sms.segments import MAX_SEGMENTS, Encoding

Instruction = Literal[
    "make_professional",
    "make_friendly",
    "make_formal",
    "make_casual",
    "shorten",
    "improve_clarity",
    "fix_grammar",
    "adjust_tone",
]
Tone = Literal["formal", "casual", "friendly", "professional"]
SummaryLength = Literal["short", "medium", "long"]
Decision = Literal["accepted", "edited", "dismissed"]

Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_CHARS)
]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _known_language(value: str | None) -> str | None:
    if value is not None and value not in LANGUAGES:
        raise ValueError("Unsupported language code")
    return value


class SuggestRepliesRequest(_Request):
    conversation_id: UUID
    context_message_count: int = Field(default=10, ge=1, le=MAX_CONTEXT_MESSAGES)
    count: int = Field(default=3, ge=1, le=5)


class TranslateRequest(_Request):
    text: Text
    target_language: str
    source_language: str | None = None

    @field_validator("target_language", "source_language")
    @classmethod
    def _supported(cls, value: str | None) -> str | None:
        return _known_language(value)

    @model_validator(mode="after")
    def _different(self) -> Self:
        if self.source_language == self.target_language:
            raise ValueError("Source and target language must differ")
        return self


class RewriteRequest(_Request):
    text: Text
    instruction: Instruction
    # Required when instruction is adjust_tone, ignored otherwise.
    tone: Tone | None = None

    @model_validator(mode="after")
    def _tone_pairing(self) -> Self:
        if self.instruction == "adjust_tone" and self.tone is None:
            raise ValueError("tone is required when instruction is adjust_tone")
        return self


class OptimiseSmsRequest(_Request):
    text: Text
    max_segments: int = Field(default=1, ge=1, le=MAX_SEGMENTS)


class SummariseRequest(_Request):
    conversation_id: UUID
    message_count: int = Field(default=20, ge=2, le=MAX_SUMMARY_MESSAGES)
    length: SummaryLength = "medium"


class ComposeRequest(_Request):
    prompt: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_PROMPT_CHARS)
    ]
    context: list[Annotated[str, StringConstraints(max_length=MAX_CONTEXT_LINE_CHARS)]] = Field(
        default_factory=list, max_length=5
    )
    max_length: int | None = Field(default=None, ge=20, le=MAX_TEXT_CHARS)
    language: str | None = None

    @field_validator("language")
    @classmethod
    def _supported(cls, value: str | None) -> str | None:
        return _known_language(value)


class DecisionRequest(_Request):
    decision: Decision


class AiSettingsRequest(_Request):
    enabled: bool


# -- responses ---------------------------------------------------------------------------------


class AiMeta(BaseModel):
    """Present on every draft. `assistance_id` is what the user's decision is reported against."""

    assistance_id: UUID | None
    model_id: str
    latency_ms: int
    simulated: bool
    # Set when no usable draft came back (empty or invalid model output).
    message: str | None = None


class SuggestRepliesOut(AiMeta):
    suggestions: list[str]


class TranslateOut(AiMeta):
    original_text: str
    translated_text: str | None
    source_language: str | None
    target_language: str


class RewriteOut(AiMeta):
    original_text: str
    rewritten_text: str | None
    instruction: Instruction


class SegmentCount(BaseModel):
    characters: int
    units: int
    segments: int
    encoding: Encoding


class OptimiseSmsOut(AiMeta):
    original_text: str
    optimised_text: str | None
    original: SegmentCount
    optimised: SegmentCount | None
    max_segments: int
    within_target: bool
    # The model's own claim. It is not verified: the user must read the draft before sending.
    meaning_preserved: bool | None


class SummariseOut(AiMeta):
    summary: str | None
    messages_summarised: int


class ComposeOut(AiMeta):
    composed_text: str | None
    character_count: int
    segments: SegmentCount | None


class DecisionOut(BaseModel):
    assistance_id: UUID
    decision: Decision


class LanguageOut(BaseModel):
    code: str
    name: str


class AiStatusOut(BaseModel):
    # Platform kill switch (admin). When false, nothing in the assistant works.
    available: bool
    # This user's opt-in. Defaults to off until the user turns it on.
    enabled: bool
    # True for the mock provider: outputs are canned demo text, not a real model.
    simulated: bool
    model_id: str
    languages: list[LanguageOut]
    max_text_chars: int
