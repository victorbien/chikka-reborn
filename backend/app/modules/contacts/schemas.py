"""Request and response models for Module B (contacts and buddy list)."""

import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.sanitize import clean_text

# "unknown" means the contact does not share presence with you. It is never shown as offline.
ContactPresence = Literal["online", "away", "busy", "offline", "unknown"]
ContactFilter = Literal["all", "online", "offline", "favourites", "group"]
Relationship = Literal["none", "contact", "request_sent", "request_received"]

_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


# -- people ----------------------------------------------------------------------------------


class PersonCard(BaseModel):
    """The minimum that identifies an account to someone who is not (yet) a contact."""

    user_id: UUID
    username: str | None
    display_name: str
    avatar_url: str | None


class SearchPerson(PersonCard):
    relationship: Relationship
    contact_id: UUID | None = None
    request_id: UUID | None = None


class ContactSummary(BaseModel):
    id: UUID
    contact_type: Literal["chikka", "sms"]
    user_id: UUID | None
    username: str | None
    display_name: str
    nickname: str | None
    avatar_url: str | None
    status_message: str | None
    presence: ContactPresence
    last_seen_at: datetime | None
    is_favourite: bool
    group_ids: list[UUID]
    masked_phone: str | None


class ContactDetail(ContactSummary):
    bio: str | None
    country_code: str | None
    added_at: datetime


class SearchResponse(BaseModel):
    contacts: list[ContactSummary]
    people: list[SearchPerson]


# -- contacts --------------------------------------------------------------------------------


class ContactUpdate(BaseModel):
    """PATCH /contacts/{id}. Omit a field to leave it unchanged; nickname null clears it."""

    model_config = ConfigDict(extra="forbid")

    is_favourite: bool | None = None
    nickname: str | None = None

    @field_validator("nickname")
    @classmethod
    def _nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = clean_text(value)
        if len(cleaned) > 100:
            raise ValueError("Nickname must be at most 100 characters")
        return cleaned or None

    @model_validator(mode="after")
    def _favourite_not_null(self) -> "ContactUpdate":
        if "is_favourite" in self.model_fields_set and self.is_favourite is None:
            raise ValueError("is_favourite cannot be null")
        return self


# -- requests --------------------------------------------------------------------------------


class ContactRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    note: str | None = None

    @field_validator("note")
    @classmethod
    def _note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = clean_text(value)
        if len(cleaned) > 140:
            raise ValueError("Note must be at most 140 characters")
        return cleaned or None


class ContactRequestSent(BaseModel):
    """Deliberately uninformative: it is the same whether the request was created, was
    silently ignored (blocked, private, cooling down) or was merged with a pending request."""

    status: Literal["sent", "contacts"]


class ContactRequestItem(BaseModel):
    id: UUID
    direction: Literal["incoming", "outgoing"]
    person: PersonCard
    note: str | None
    created_at: datetime
    expires_at: datetime


class AcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: UUID | None = None


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block: bool = False


# -- groups ----------------------------------------------------------------------------------


def _group_name(value: str) -> str:
    cleaned = clean_text(value)
    if not 1 <= len(cleaned) <= 30:
        raise ValueError("Group name must be 1 to 30 characters")
    return cleaned


def _group_color(value: str | None) -> str | None:
    if value is None:
        return None
    if not _COLOR.fullmatch(value):
        raise ValueError("Colour must look like #1A2B3C")
    return value.upper()


class GroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    color: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _group_name(value)

    @field_validator("color")
    @classmethod
    def _color(cls, value: str | None) -> str | None:
        return _group_color(value)


class GroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    color: str | None = None
    position: Annotated[int, Field(ge=0, le=1000)] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _group_name(value)

    @field_validator("color")
    @classmethod
    def _color(cls, value: str | None) -> str | None:
        return _group_color(value)

    @model_validator(mode="after")
    def _required_not_null(self) -> "GroupUpdate":
        for name in ("name", "position"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class GroupResponse(BaseModel):
    id: UUID
    name: str
    color: str | None
    position: int
    member_count: int


class GroupMembersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_ids: Annotated[list[UUID], Field(min_length=1, max_length=100)]


# -- blocks ----------------------------------------------------------------------------------


class BlockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID


class BlockItem(BaseModel):
    user_id: UUID
    person: PersonCard
    blocked_at: datetime


# -- recent ----------------------------------------------------------------------------------


class RecentContact(BaseModel):
    contact: ContactSummary
    conversation_id: UUID
    last_message_at: datetime


class RecentConversation(BaseModel):
    conversation_id: UUID
    conversation_type: Literal["chikka", "sms"]
    contact_id: UUID | None
    user_id: UUID | None
    display_name: str
    avatar_url: str | None
    masked_phone: str | None
    is_contact: bool
    last_message_at: datetime | None
