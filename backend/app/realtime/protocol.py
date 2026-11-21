"""Client-to-server WebSocket frames (docs/api/realtime-api.md). Unknown types are rejected."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

MAX_FRAME_BYTES = 8 * 1024


class _Frame(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthFrame(_Frame):
    type: Literal["auth"]
    token: Annotated[str, Field(min_length=1, max_length=4096)]


class RefreshFrame(_Frame):
    type: Literal["auth.refresh"]
    token: Annotated[str, Field(min_length=1, max_length=4096)]


class PingFrame(_Frame):
    type: Literal["ping"]


class AckFrame(_Frame):
    type: Literal["ack"]
    message_ids: Annotated[list[UUID], Field(min_length=1, max_length=100)]


class TypingFrame(_Frame):
    type: Literal["typing"]
    conversation_id: UUID


UplinkFrame = Annotated[
    RefreshFrame | PingFrame | AckFrame | TypingFrame, Field(discriminator="type")
]
uplink_adapter: TypeAdapter[RefreshFrame | PingFrame | AckFrame | TypingFrame] = TypeAdapter(
    UplinkFrame
)
