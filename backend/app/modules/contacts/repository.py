"""Database access for Module B. Every method that reads or writes owner-scoped rows takes the
owner id and puts it in the WHERE clause, so a caller can never reach another user's rows by
supplying an id (CC-04). Repositories never commit; the service owns the transaction."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    and_,
    delete,
    exists,
    func,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import PhoneNumber
from app.modules.contacts.models import (
    Contact,
    ContactGroup,
    ContactGroupMember,
    ContactRequest,
    UserBlock,
)
from app.modules.profiles.models import Profile


class GroupNameTakenError(Exception):
    pass


class GroupLimitReachedError(Exception):
    pass


def _sqlstate(exc: DBAPIError) -> str | None:
    original = exc.orig
    return getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)


def _not_blocked(viewer: UUID, other: Any) -> ColumnElement[bool]:
    """True when neither user has blocked the other."""
    blocked_by_viewer = exists().where(
        UserBlock.blocker_id == viewer, UserBlock.blocked_user_id == other
    )
    blocked_viewer = exists().where(
        UserBlock.blocker_id == other, UserBlock.blocked_user_id == viewer
    )
    return and_(~blocked_by_viewer, ~blocked_viewer)


@dataclass(frozen=True)
class ConversationRow:
    conversation_id: UUID
    conversation_type: str
    last_message_at: datetime | None
    remote_phone: str | None
    other_user_id: UUID | None


class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- contacts ----------------------------------------------------------------------------

    def _visible_contacts(self, owner_id: UUID) -> Any:
        return (
            select(Contact, Profile)
            .outerjoin(Profile, Profile.id == Contact.contact_user_id)
            .where(
                Contact.owner_id == owner_id,
                or_(
                    Contact.contact_type == "sms",
                    and_(
                        Profile.status == "active",
                        _not_blocked(owner_id, Contact.contact_user_id),
                    ),
                ),
            )
        )

    async def list_contacts(
        self, owner_id: UUID, *, group_id: UUID | None = None
    ) -> list[tuple[Contact, Profile | None]]:
        statement = self._visible_contacts(owner_id)
        if group_id is not None:
            statement = statement.join(
                ContactGroupMember,
                and_(
                    ContactGroupMember.contact_id == Contact.id,
                    ContactGroupMember.group_id == group_id,
                    ContactGroupMember.owner_id == owner_id,
                ),
            )
        rows = (await self._session.execute(statement)).all()
        return [(row[0], row[1]) for row in rows]

    async def search_contacts(
        self, owner_id: UUID, term: str, limit: int
    ) -> list[tuple[Contact, Profile | None]]:
        statement = (
            self._visible_contacts(owner_id)
            .where(
                or_(
                    Contact.display_name.icontains(term, autoescape=True),
                    Profile.display_name.icontains(term, autoescape=True),
                    Profile.username.icontains(term, autoescape=True),
                )
            )
            .order_by(func.lower(func.coalesce(Contact.display_name, Profile.display_name)))
            .limit(limit)
        )
        return [(row[0], row[1]) for row in (await self._session.execute(statement)).all()]

    async def get_contact(
        self, owner_id: UUID, contact_id: UUID
    ) -> tuple[Contact, Profile | None] | None:
        statement = self._visible_contacts(owner_id).where(Contact.id == contact_id)
        row = (await self._session.execute(statement)).first()
        return None if row is None else (row[0], row[1])

    async def get_owned_contact(self, owner_id: UUID, contact_id: UUID) -> Contact | None:
        """The raw row, including blocked contacts (so they can still be removed)."""
        statement = select(Contact).where(Contact.id == contact_id, Contact.owner_id == owner_id)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def contact_for_user(self, owner_id: UUID, user_id: UUID) -> Contact | None:
        statement = select(Contact).where(
            Contact.owner_id == owner_id, Contact.contact_user_id == user_id
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def contact_rows_for_users(
        self, owner_id: UUID, user_ids: Sequence[UUID]
    ) -> dict[UUID, tuple[Contact, Profile]]:
        if not user_ids:
            return {}
        statement = self._visible_contacts(owner_id).where(Contact.contact_user_id.in_(user_ids))
        result: dict[UUID, tuple[Contact, Profile]] = {}
        for contact, profile in (
            (row[0], row[1]) for row in await self._session.execute(statement)
        ):
            if profile is not None and contact.contact_user_id is not None:
                result[contact.contact_user_id] = (contact, profile)
        return result

    async def sms_contacts_by_phone(
        self, owner_id: UUID, phones: Sequence[str]
    ) -> dict[str, Contact]:
        if not phones:
            return {}
        statement = select(Contact).where(
            Contact.owner_id == owner_id, Contact.phone_e164.in_(phones)
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return {row.phone_e164: row for row in rows if row.phone_e164 is not None}

    async def apply_contact(self, contact: Contact, changes: dict[str, Any]) -> Contact:
        for field, value in changes.items():
            setattr(contact, field, value)
        await self._session.flush()
        await self._session.refresh(contact)
        return contact

    async def remove_pair(self, user_a: UUID, user_b: UUID) -> int:
        """Delete both directions of a Chikka relationship. Group memberships cascade."""
        statement = delete(Contact).where(
            or_(
                and_(Contact.owner_id == user_a, Contact.contact_user_id == user_b),
                and_(Contact.owner_id == user_b, Contact.contact_user_id == user_a),
            )
        )
        result = await self._session.execute(statement)
        return int(getattr(result, "rowcount", 0))

    async def remove_owned(self, owner_id: UUID, contact_id: UUID) -> int:
        result = await self._session.execute(
            delete(Contact).where(Contact.id == contact_id, Contact.owner_id == owner_id)
        )
        return int(getattr(result, "rowcount", 0))

    async def clear_recent(self, owner_id: UUID) -> None:
        await self._session.execute(
            update(Contact).where(Contact.owner_id == owner_id).values(recent_cleared_at=func.now())
        )

    # -- profiles and discovery --------------------------------------------------------------

    async def profiles_by_ids(self, user_ids: Sequence[UUID]) -> dict[UUID, Profile]:
        if not user_ids:
            return {}
        statement = select(Profile).where(Profile.id.in_(set(user_ids)))
        return {p.id: p for p in (await self._session.execute(statement)).scalars()}

    async def active_profile(self, user_id: UUID) -> Profile | None:
        statement = select(Profile).where(Profile.id == user_id, Profile.status == "active")
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def profile_by_username(self, username: str) -> Profile | None:
        statement = select(Profile).where(
            func.lower(Profile.username) == username.lower(),
            Profile.status == "active",
            Profile.onboarding_completed_at.is_not(None),
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def user_id_by_email(self, email: str) -> UUID | None:
        result = await self._session.execute(
            text("select private.find_user_id_by_email(:email)"), {"email": email}
        )
        value = result.scalar_one_or_none()
        return None if value is None else UUID(str(value))

    async def user_id_by_verified_phone(self, e164: str) -> UUID | None:
        statement = (
            select(PhoneNumber.user_id)
            .where(PhoneNumber.e164 == e164, PhoneNumber.status == "verified")
            .limit(1)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    # -- blocks ------------------------------------------------------------------------------

    async def blocked_between(self, user_a: UUID, user_b: UUID) -> bool:
        statement = select(
            exists().where(
                or_(
                    and_(UserBlock.blocker_id == user_a, UserBlock.blocked_user_id == user_b),
                    and_(UserBlock.blocker_id == user_b, UserBlock.blocked_user_id == user_a),
                )
            )
        )
        return bool((await self._session.execute(statement)).scalar_one())

    async def blocked_user_ids(self, user_id: UUID, others: Sequence[UUID]) -> set[UUID]:
        """Those of `others` who have blocked, or are blocked by, the given user."""
        if not others:
            return set()
        ids = set(others)
        by_user = select(UserBlock.blocked_user_id).where(
            UserBlock.blocker_id == user_id, UserBlock.blocked_user_id.in_(ids)
        )
        blocking_user = select(UserBlock.blocker_id).where(
            UserBlock.blocked_user_id == user_id, UserBlock.blocker_id.in_(ids)
        )
        found: set[UUID] = set()
        for statement in (by_user, blocking_user):
            found.update(i for i in (await self._session.execute(statement)).scalars() if i)
        return found

    async def has_blocked(self, blocker_id: UUID, target_id: UUID) -> bool:
        statement = select(
            exists().where(
                UserBlock.blocker_id == blocker_id, UserBlock.blocked_user_id == target_id
            )
        )
        return bool((await self._session.execute(statement)).scalar_one())

    async def add_block(self, blocker_id: UUID, target_id: UUID) -> bool:
        statement = (
            pg_insert(UserBlock)
            .values(blocker_id=blocker_id, blocked_user_id=target_id)
            .on_conflict_do_nothing(constraint="uq_user_blocks_user")
        )
        result = await self._session.execute(statement)
        return bool(getattr(result, "rowcount", 0))

    async def remove_block(self, blocker_id: UUID, target_id: UUID) -> int:
        result = await self._session.execute(
            delete(UserBlock).where(
                UserBlock.blocker_id == blocker_id, UserBlock.blocked_user_id == target_id
            )
        )
        return int(getattr(result, "rowcount", 0))

    async def list_blocks(self, blocker_id: UUID) -> list[tuple[UserBlock, Profile]]:
        statement = (
            select(UserBlock, Profile)
            .join(Profile, Profile.id == UserBlock.blocked_user_id)
            .where(UserBlock.blocker_id == blocker_id)
            .order_by(UserBlock.created_at.desc())
        )
        return [(row[0], row[1]) for row in (await self._session.execute(statement)).all()]

    # -- requests ----------------------------------------------------------------------------

    async def pending_between(
        self, user_a: UUID, user_b: UUID, *, lock: bool = False
    ) -> ContactRequest | None:
        statement = select(ContactRequest).where(
            ContactRequest.status == "pending",
            or_(
                and_(ContactRequest.from_user_id == user_a, ContactRequest.to_user_id == user_b),
                and_(ContactRequest.from_user_id == user_b, ContactRequest.to_user_id == user_a),
            ),
        )
        if lock:
            statement = statement.with_for_update()
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def last_rejection_at(self, from_user: UUID, to_user: UUID) -> datetime | None:
        statement = select(func.max(ContactRequest.responded_at)).where(
            ContactRequest.from_user_id == from_user,
            ContactRequest.to_user_id == to_user,
            ContactRequest.status == "rejected",
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def create_request(
        self, from_user: UUID, to_user: UUID, note: str | None
    ) -> ContactRequest | None:
        """None when a concurrent request already holds the unique pending slot."""
        request = ContactRequest(from_user_id=from_user, to_user_id=to_user, note=note)
        self._session.add(request)
        try:
            async with self._session.begin_nested():
                await self._session.flush()
        except IntegrityError as exc:
            if _sqlstate(exc) == "23505":
                self._session.expunge(request)
                return None
            raise
        await self._session.refresh(request)
        return request

    async def get_request_for_update(self, request_id: UUID) -> ContactRequest | None:
        statement = select(ContactRequest).where(ContactRequest.id == request_id).with_for_update()
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def set_request_status(self, request: ContactRequest, status: str) -> None:
        request.status = status
        if status != "expired":
            request.responded_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(request)

    async def cancel_pending_between(self, user_a: UUID, user_b: UUID) -> None:
        await self._session.execute(
            update(ContactRequest)
            .where(
                ContactRequest.status == "pending",
                or_(
                    and_(
                        ContactRequest.from_user_id == user_a, ContactRequest.to_user_id == user_b
                    ),
                    and_(
                        ContactRequest.from_user_id == user_b, ContactRequest.to_user_id == user_a
                    ),
                ),
            )
            .values(status="cancelled", responded_at=func.now())
        )

    async def list_requests(
        self, user_id: UUID, *, incoming: bool, offset: int, limit: int
    ) -> tuple[list[tuple[ContactRequest, Profile]], int]:
        own = ContactRequest.to_user_id if incoming else ContactRequest.from_user_id
        other = ContactRequest.from_user_id if incoming else ContactRequest.to_user_id
        conditions = [
            own == user_id,
            ContactRequest.status == "pending",
            ContactRequest.expires_at > func.now(),
            Profile.status == "active",
        ]
        if incoming:
            # A sender the recipient blocked never reaches the inbox.
            conditions.append(_not_blocked(user_id, other))
        base = select(ContactRequest, Profile).join(Profile, Profile.id == other).where(*conditions)
        total = (
            await self._session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self._session.execute(
                base.order_by(ContactRequest.created_at.desc()).offset(offset).limit(limit)
            )
        ).all()
        return [(row[0], row[1]) for row in rows], int(total)

    async def accept_request(self, request_id: UUID, acting_user_id: UUID) -> None:
        """Atomic accept: status change plus both contact rows (private.accept_contact_request)."""
        await self._session.execute(
            text("select private.accept_contact_request(:request_id, :user_id)"),
            {"request_id": request_id, "user_id": acting_user_id},
        )

    # -- groups ------------------------------------------------------------------------------

    async def list_groups(self, owner_id: UUID) -> list[tuple[ContactGroup, int]]:
        statement = (
            select(ContactGroup, func.count(ContactGroupMember.contact_id))
            .outerjoin(ContactGroupMember, ContactGroupMember.group_id == ContactGroup.id)
            .where(ContactGroup.owner_id == owner_id)
            .group_by(ContactGroup.id)
            .order_by(ContactGroup.position, func.lower(ContactGroup.name))
        )
        return [(row[0], int(row[1])) for row in (await self._session.execute(statement)).all()]

    async def get_group(self, owner_id: UUID, group_id: UUID) -> ContactGroup | None:
        statement = select(ContactGroup).where(
            ContactGroup.id == group_id, ContactGroup.owner_id == owner_id
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def member_count(self, group_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(ContactGroupMember)
            .where(ContactGroupMember.group_id == group_id)
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def _flush_group(self) -> None:
        try:
            async with self._session.begin_nested():
                await self._session.flush()
        except DBAPIError as exc:
            if isinstance(exc, IntegrityError) and _sqlstate(exc) == "23505":
                raise GroupNameTakenError from exc
            if "GROUP_LIMIT_REACHED" in str(exc):
                raise GroupLimitReachedError from exc
            raise

    async def create_group(self, owner_id: UUID, name: str, color: str | None) -> ContactGroup:
        group = ContactGroup(owner_id=owner_id, name=name, color=color)
        self._session.add(group)
        await self._flush_group()
        await self._session.refresh(group)
        return group

    async def apply_group(self, group: ContactGroup, changes: dict[str, Any]) -> ContactGroup:
        for field, value in changes.items():
            setattr(group, field, value)
        await self._flush_group()
        await self._session.refresh(group)
        return group

    async def delete_group(self, group: ContactGroup) -> None:
        await self._session.delete(group)
        await self._session.flush()

    async def owned_contact_ids(self, owner_id: UUID, contact_ids: Sequence[UUID]) -> set[UUID]:
        statement = select(Contact.id).where(
            Contact.owner_id == owner_id, Contact.id.in_(set(contact_ids))
        )
        return set((await self._session.execute(statement)).scalars())

    async def add_members(
        self, owner_id: UUID, group_id: UUID, contact_ids: Sequence[UUID]
    ) -> None:
        statement = (
            pg_insert(ContactGroupMember)
            .values(
                [
                    {"group_id": group_id, "contact_id": contact_id, "owner_id": owner_id}
                    for contact_id in dict.fromkeys(contact_ids)
                ]
            )
            .on_conflict_do_nothing(constraint="pk_contact_group_members")
        )
        await self._session.execute(statement)

    async def remove_member(self, owner_id: UUID, group_id: UUID, contact_id: UUID) -> int:
        result = await self._session.execute(
            delete(ContactGroupMember).where(
                ContactGroupMember.group_id == group_id,
                ContactGroupMember.contact_id == contact_id,
                ContactGroupMember.owner_id == owner_id,
            )
        )
        return int(getattr(result, "rowcount", 0))

    async def group_ids_by_contact(
        self, owner_id: UUID, contact_ids: Sequence[UUID]
    ) -> dict[UUID, list[UUID]]:
        if not contact_ids:
            return {}
        statement = select(ContactGroupMember.contact_id, ContactGroupMember.group_id).where(
            ContactGroupMember.owner_id == owner_id,
            ContactGroupMember.contact_id.in_(set(contact_ids)),
        )
        grouped: dict[UUID, list[UUID]] = {}
        for contact_id, group_id in (await self._session.execute(statement)).all():
            grouped.setdefault(contact_id, []).append(group_id)
        return grouped

    # -- conversations (read only; the chat module owns writes) ------------------------------

    async def recent_conversations(self, user_id: UUID, limit: int) -> list[ConversationRow]:
        result = await self._session.execute(
            text(
                """
                select c.id as conversation_id, c.conversation_type, c.last_message_at,
                       c.remote_phone::text as remote_phone, other.user_id as other_user_id
                from public.conversation_members me
                join public.conversations c on c.id = me.conversation_id
                left join public.conversation_members other
                  on other.conversation_id = c.id and other.user_id <> me.user_id
                where me.user_id = :user_id
                  and me.left_at is null
                  and c.last_message_at is not null
                order by c.last_message_at desc
                limit :limit
                """
            ),
            {"user_id": user_id, "limit": limit},
        )
        return [
            ConversationRow(
                conversation_id=row.conversation_id,
                conversation_type=row.conversation_type,
                last_message_at=row.last_message_at,
                remote_phone=row.remote_phone,
                other_user_id=row.other_user_id,
            )
            for row in result
        ]
