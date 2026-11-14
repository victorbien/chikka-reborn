"""Contacts, requests, groups, blocks and the buddy list (FR-CONTACTS-001..014).

Rules this module enforces:
* Every read and write is scoped to the authenticated caller; ids from the client are only
  ever looked up inside the caller's own rows (CC-04). A foreign id looks exactly like a
  missing one (404).
* Discovery never reveals whether an email address, number or username is registered. A
  search for something that is missing, private, not discoverable or blocked all return the
  same empty result (FR-CONTACTS-007, FR-PRIVACY-005).
* A block is silent. The blocked party sees the same neutral responses as before.
"""

import asyncio
import logging
import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from app.core.privacy import mask_phone
from app.core.sanitize import clean_text
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.integrations.storage_provider import StorageError, StorageProvider
from app.modules.audit.service import AuditLogger
from app.modules.auth.phone_service import normalise_phone
from app.modules.contacts.models import Contact, ContactGroup, ContactRequest
from app.modules.contacts.repository import (
    ContactRepository,
    GroupLimitReachedError,
    GroupNameTakenError,
)
from app.modules.contacts.schemas import (
    BlockItem,
    ContactDetail,
    ContactFilter,
    ContactPresence,
    ContactRequestCreate,
    ContactRequestItem,
    ContactRequestSent,
    ContactSummary,
    ContactUpdate,
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    PersonCard,
    RecentContact,
    RecentConversation,
    SearchPerson,
    SearchResponse,
)
from app.modules.notifications.service import create_notification
from app.modules.profiles.models import Profile
from app.modules.profiles.presence import PresenceRegistry
from app.modules.profiles.schemas import PresencePreference
from app.modules.rate_limits import service as limits
from app.modules.rate_limits.service import RateLimiter

logger = logging.getLogger(__name__)

AVATAR_URL_TTL_SECONDS = 3600
MIN_SEARCH_LENGTH = 2
SEARCH_RESULT_LIMIT = 20
RECENT_LIMIT = 20
RESEND_AFTER_REJECTION = timedelta(days=7)
_USERNAME = re.compile(r"^[A-Za-z0-9_]{3,20}$")

_PRESENCE: dict[str, ContactPresence] = {
    "online": "online",
    "away": "away",
    "busy": "busy",
    "offline": "offline",
    "invisible": "offline",
}
_ONLINE: frozenset[ContactPresence] = frozenset({"online", "away", "busy"})

_REQUEST_UNAVAILABLE = "This request is no longer available."


def _display_name(contact: Contact, profile: Profile | None) -> str:
    if contact.display_name:
        return contact.display_name
    return profile.display_name if profile is not None else "Unknown"


def _sort_key(item: tuple[Contact, Profile | None]) -> tuple[bool, str, str]:
    contact, profile = item
    # Favourites first, then alphabetical (FR-CONTACTS-003). The id keeps the order stable.
    return (not contact.is_favourite, _display_name(contact, profile).casefold(), str(contact.id))


class ContactService:
    def __init__(
        self,
        *,
        database: Database,
        storage: StorageProvider,
        limiter: RateLimiter,
        audit: AuditLogger,
        presence: PresenceRegistry,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._db = database
        self._storage = storage
        self._limiter = limiter
        self._audit = audit
        self._presence = presence
        self._clock = clock

    # -- shared helpers ----------------------------------------------------------------------

    async def _sign(self, path: str | None) -> str | None:
        if not path:
            return None
        try:
            return await self._storage.signed_url(path, AVATAR_URL_TTL_SECONDS)
        except StorageError:
            return None  # The UI falls back to initials.

    async def _avatar_urls(self, profiles: Iterable[Profile]) -> dict[UUID, str | None]:
        unique = {profile.id: profile.avatar_path for profile in profiles}
        urls = await asyncio.gather(*(self._sign(path) for path in unique.values()))
        return dict(zip(unique.keys(), urls, strict=True))

    def _presence_of(self, profile: Profile) -> tuple[ContactPresence, datetime | None]:
        """Presence as a contact may see it. 'nobody' hides it entirely (never shown as offline)."""
        if profile.share_presence == "nobody":
            return "unknown", None
        live = self._presence.status(
            str(profile.id),
            cast(PresencePreference, profile.presence_preference),
        )
        seen = _PRESENCE[self._presence.as_seen_by_others(live)]
        return seen, profile.last_seen_at if profile.show_last_seen else None

    def _summary(
        self,
        contact: Contact,
        profile: Profile | None,
        group_ids: list[UUID],
        avatar_url: str | None,
    ) -> ContactSummary:
        if profile is None:
            return ContactSummary(
                id=contact.id,
                contact_type="sms",
                user_id=None,
                username=None,
                display_name=_display_name(contact, None),
                nickname=contact.display_name,
                avatar_url=None,
                status_message=None,
                presence="unknown",
                last_seen_at=None,
                is_favourite=contact.is_favourite,
                group_ids=group_ids,
                masked_phone=mask_phone(contact.phone_e164) if contact.phone_e164 else None,
            )
        presence, last_seen = self._presence_of(profile)
        # A private profile still identifies itself to its contacts, but shares nothing else.
        shares_details = profile.profile_visibility != "private"
        return ContactSummary(
            id=contact.id,
            contact_type="chikka",
            user_id=profile.id,
            username=profile.username,
            display_name=_display_name(contact, profile),
            nickname=contact.display_name,
            avatar_url=avatar_url,
            status_message=profile.status_message if shares_details else None,
            presence=presence,
            last_seen_at=last_seen,
            is_favourite=contact.is_favourite,
            group_ids=group_ids,
            masked_phone=None,
        )

    async def _summaries(
        self,
        repository: ContactRepository,
        owner_id: UUID,
        rows: list[tuple[Contact, Profile | None]],
    ) -> tuple[list[tuple[Contact, Profile | None, list[UUID]]], list[Profile]]:
        group_map = await repository.group_ids_by_contact(owner_id, [c.id for c, _ in rows])
        enriched = [(c, p, group_map.get(c.id, [])) for c, p in rows]
        return enriched, [p for _, p in rows if p is not None]

    def _card(self, profile: Profile, avatars: dict[UUID, str | None]) -> PersonCard:
        return PersonCard(
            user_id=profile.id,
            username=profile.username,
            display_name=profile.display_name,
            avatar_url=avatars.get(profile.id),
        )

    async def _write_limit(self, user: AuthenticatedUser) -> None:
        await self._limiter.hit(limits.CONTACT_WRITE_PER_USER, str(user.id))

    # -- buddy list --------------------------------------------------------------------------

    async def list_contacts(
        self,
        user: AuthenticatedUser,
        *,
        contact_filter: ContactFilter,
        group_id: UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ContactSummary], int]:
        if contact_filter == "group" and group_id is None:
            raise UnprocessableError(
                "Choose a group to filter by.",
                details={"problems": [{"field": "query.group_id", "reason": "Required"}]},
            )
        scope_group = group_id if contact_filter == "group" else None
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            if scope_group is not None and await repository.get_group(user.id, scope_group) is None:
                raise NotFoundError("Group not found.")
            rows = await repository.list_contacts(user.id, group_id=scope_group)

            selected: list[tuple[Contact, Profile | None]] = []
            for contact, profile in rows:
                presence = self._presence_of(profile)[0] if profile is not None else None
                if contact_filter == "favourites" and not contact.is_favourite:
                    continue
                if contact_filter == "online" and presence not in _ONLINE:
                    continue
                if contact_filter == "offline" and presence not in ("offline", "unknown"):
                    continue
                selected.append((contact, profile))
            selected.sort(key=_sort_key)

            start = (page - 1) * page_size
            window = selected[start : start + page_size]
            enriched, profiles = await self._summaries(repository, user.id, window)
        avatars = await self._avatar_urls(profiles)
        items = [
            self._summary(c, p, groups, avatars.get(p.id) if p else None)
            for c, p, groups in enriched
        ]
        return items, len(selected)

    async def get_contact(self, user: AuthenticatedUser, contact_id: UUID) -> ContactDetail:
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            found = await repository.get_contact(user.id, contact_id)
            if found is None:
                raise NotFoundError("Contact not found.")
            contact, profile = found
            enriched, profiles = await self._summaries(repository, user.id, [found])
        avatars = await self._avatar_urls(profiles)
        summary = self._summary(
            contact, profile, enriched[0][2], avatars.get(profile.id) if profile else None
        )
        shares_details = profile is not None and profile.profile_visibility != "private"
        return ContactDetail(
            **summary.model_dump(),
            bio=profile.bio if profile is not None and shares_details else None,
            country_code=profile.country_code if profile is not None else None,
            added_at=contact.created_at,
        )

    async def update_contact(
        self, user: AuthenticatedUser, contact_id: UUID, request: ContactUpdate
    ) -> ContactDetail:
        changes: dict[str, object] = {}
        if "is_favourite" in request.model_fields_set:
            changes["is_favourite"] = request.is_favourite
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            contact = await repository.get_owned_contact(user.id, contact_id)
            if contact is None:
                raise NotFoundError("Contact not found.")
            if "nickname" in request.model_fields_set:
                if request.nickname is None and contact.contact_type == "sms":
                    raise UnprocessableError(
                        "A phone contact needs a name.",
                        details={"problems": [{"field": "body.nickname", "reason": "Required"}]},
                    )
                changes["display_name"] = request.nickname
            if changes:
                await repository.apply_contact(contact, changes)
        return await self.get_contact(user, contact_id)

    async def remove_contact(self, user: AuthenticatedUser, contact_id: UUID) -> None:
        """Removing a Chikka contact ends the mutual relationship for both people."""
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            contact = await repository.get_owned_contact(user.id, contact_id)
            if contact is None:
                raise NotFoundError("Contact not found.")
            if contact.contact_user_id is not None:
                await repository.remove_pair(user.id, contact.contact_user_id)
            else:
                await repository.remove_owned(user.id, contact.id)
            await self._audit.record(
                session,
                category="privacy",
                action="contact.removed",
                actor_id=user.id,
                target_type="contact",
                target_id=str(contact_id),
            )

    # -- discovery ---------------------------------------------------------------------------

    async def search(self, user: AuthenticatedUser, query: str) -> SearchResponse:
        term = clean_text(query)
        if len(term) < MIN_SEARCH_LENGTH:
            raise UnprocessableError(
                "Type at least 2 characters to search.",
                code="query_too_short",
                details={"problems": [{"field": "query.q", "reason": "Too short"}]},
            )
        await self._limiter.hit(limits.CONTACT_SEARCH_PER_USER, str(user.id))
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            rows = await repository.search_contacts(user.id, term, SEARCH_RESULT_LIMIT)
            enriched, profiles = await self._summaries(repository, user.id, rows)
            candidate = await self._discover(repository, user, term)
            person_relationship: tuple[str, UUID | None, UUID | None] = ("none", None, None)
            if candidate is not None:
                profiles.append(candidate)
                person_relationship = await self._relationship(repository, user, candidate)
        avatars = await self._avatar_urls(profiles)
        contacts = [
            self._summary(c, p, groups, avatars.get(p.id) if p else None)
            for c, p, groups in enriched
        ]
        people: list[SearchPerson] = []
        if candidate is not None:
            relationship, contact_id, request_id = person_relationship
            people.append(
                SearchPerson(
                    **self._card(candidate, avatars).model_dump(),
                    relationship=relationship,
                    contact_id=contact_id,
                    request_id=request_id,
                )
            )
        return SearchResponse(contacts=contacts, people=people)

    async def _discover(
        self, repository: ContactRepository, user: AuthenticatedUser, term: str
    ) -> Profile | None:
        """Resolve an exact username, email or number to a discoverable account, or None.

        None is returned for every reason a lookup can fail, so callers cannot tell them apart.
        """
        candidate: Profile | None = None
        if "@" in term:
            found = await repository.user_id_by_email(term.lower())
            profile = await repository.active_profile(found) if found else None
            if profile is not None and profile.discoverable_by_email:
                candidate = profile
        elif term.startswith("+"):
            try:
                e164, _ = normalise_phone(term)
            except UnprocessableError:
                return None
            found = await repository.user_id_by_verified_phone(e164)
            profile = await repository.active_profile(found) if found else None
            if profile is not None and profile.discoverable_by_phone:
                candidate = profile
        elif _USERNAME.fullmatch(term):
            candidate = await repository.profile_by_username(term)

        if (
            candidate is None
            or candidate.id == user.id
            or candidate.profile_visibility == "private"
            or candidate.onboarding_completed_at is None
            or await repository.blocked_between(user.id, candidate.id)
        ):
            return None
        return candidate

    async def _relationship(
        self, repository: ContactRepository, user: AuthenticatedUser, other: Profile
    ) -> tuple[str, UUID | None, UUID | None]:
        existing = await repository.contact_for_user(user.id, other.id)
        if existing is not None:
            return "contact", existing.id, None
        pending = await repository.pending_between(user.id, other.id)
        if pending is not None and pending.expires_at > self._clock():
            if pending.from_user_id == user.id:
                return "request_sent", None, pending.id
            return "request_received", None, pending.id
        return "none", None, None

    # -- requests ----------------------------------------------------------------------------

    async def _notify_accepted(
        self,
        session: AsyncSession,
        repository: ContactRepository,
        accepter_id: UUID,
        pending: ContactRequest,
    ) -> None:
        """Tell the person who asked that the request was accepted (once per request)."""
        accepter = await repository.active_profile(accepter_id)
        requester = (
            pending.from_user_id if pending.to_user_id == accepter_id else pending.to_user_id
        )
        name = accepter.display_name if accepter else "Someone"
        await create_notification(
            session,
            user_id=requester,
            notification_type="contact_accepted",
            title=f"{name} accepted your contact request",
            reference_type="contact_request",
            reference_id=pending.id,
            dedupe_key=f"contact_accepted:{pending.id}",
            now=self._clock(),
        )

    async def send_request(
        self, user: AuthenticatedUser, request: ContactRequestCreate
    ) -> ContactRequestSent:
        await self._limiter.hit(limits.CONTACT_REQUEST_PER_USER, str(user.id))
        if request.user_id == user.id:
            raise UnprocessableError(
                "You can't add yourself.",
                details={"problems": [{"field": "body.user_id", "reason": "Not allowed"}]},
            )
        neutral = ContactRequestSent(status="sent")
        now = self._clock()
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            target = await repository.active_profile(request.user_id)
            if target is None or target.onboarding_completed_at is None:
                return neutral
            if await repository.contact_for_user(user.id, target.id) is not None:
                return ContactRequestSent(status="contacts")
            if await repository.has_blocked(user.id, target.id):
                raise ConflictError(
                    "You blocked this person. Unblock them to send a request.",
                    code="user_blocked",
                )
            if await repository.has_blocked(target.id, user.id) or (
                target.profile_visibility == "private"
            ):
                return neutral  # Silent: the sender learns nothing.

            pending = await repository.pending_between(user.id, target.id, lock=True)
            if pending is not None and pending.expires_at <= now:
                await repository.set_request_status(pending, "expired")
                pending = None
            if pending is not None:
                if pending.from_user_id == user.id:
                    return neutral  # Duplicate: idempotent.
                # They already asked you: asking back means yes (FR-CONTACTS-001 alt A).
                await repository.accept_request(pending.id, user.id)
                await self._audit.record(
                    session,
                    category="privacy",
                    action="contact.request_accepted",
                    actor_id=user.id,
                    target_type="user",
                    target_id=str(target.id),
                    metadata={"via": "reverse_request"},
                )
                await self._notify_accepted(session, repository, user.id, pending)
                return ContactRequestSent(status="contacts")

            rejected_at = await repository.last_rejection_at(user.id, target.id)
            if rejected_at is not None and now - rejected_at < RESEND_AFTER_REJECTION:
                return neutral  # Cooling down. No signal that it was rejected.

            created = await repository.create_request(user.id, target.id, request.note)
            if created is not None:
                await self._audit.record(
                    session,
                    category="privacy",
                    action="contact.request_sent",
                    actor_id=user.id,
                    target_type="user",
                    target_id=str(target.id),
                )
                sender = await repository.active_profile(user.id)
                sender_name = sender.display_name if sender else "Someone"
                await create_notification(
                    session,
                    user_id=target.id,
                    notification_type="contact_request",
                    title=f"{sender_name} sent you a contact request",
                    reference_type="contact_request",
                    reference_id=created.id,
                    dedupe_key=f"contact_request:{created.id}",
                    now=now,
                )
        return neutral

    async def list_requests(
        self,
        user: AuthenticatedUser,
        *,
        incoming: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[ContactRequestItem], int]:
        async with self._db.transaction() as session:
            rows, total = await ContactRepository(session).list_requests(
                user.id, incoming=incoming, offset=(page - 1) * page_size, limit=page_size
            )
        avatars = await self._avatar_urls(profile for _, profile in rows)
        items = [
            ContactRequestItem(
                id=request.id,
                direction="incoming" if incoming else "outgoing",
                person=self._card(profile, avatars),
                note=request.note,
                created_at=request.created_at,
                expires_at=request.expires_at,
            )
            for request, profile in rows
        ]
        return items, total

    async def accept_request(
        self, user: AuthenticatedUser, request_id: UUID, group_id: UUID | None
    ) -> ContactDetail:
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            pending = await repository.get_request_for_update(request_id)
            if pending is None or pending.to_user_id != user.id:
                raise NotFoundError("Request not found.")
            if group_id is not None and await repository.get_group(user.id, group_id) is None:
                raise NotFoundError("Group not found.")
            if pending.status != "accepted":
                if (
                    pending.status != "pending"
                    or pending.expires_at <= self._clock()
                    or await repository.blocked_between(pending.from_user_id, user.id)
                ):
                    raise ConflictError(_REQUEST_UNAVAILABLE, code="request_unavailable")
                await repository.accept_request(pending.id, user.id)
                await self._audit.record(
                    session,
                    category="privacy",
                    action="contact.request_accepted",
                    actor_id=user.id,
                    target_type="user",
                    target_id=str(pending.from_user_id),
                )
                await self._notify_accepted(session, repository, user.id, pending)
            contact = await repository.contact_for_user(user.id, pending.from_user_id)
            if contact is None:
                raise ConflictError(_REQUEST_UNAVAILABLE, code="request_unavailable")
            if group_id is not None:
                await repository.add_members(user.id, group_id, [contact.id])
            contact_id = contact.id
        return await self.get_contact(user, contact_id)

    async def reject_request(
        self, user: AuthenticatedUser, request_id: UUID, *, block: bool
    ) -> None:
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            pending = await repository.get_request_for_update(request_id)
            if pending is None or pending.to_user_id != user.id:
                raise NotFoundError("Request not found.")
            if pending.status != "pending" or pending.expires_at <= self._clock():
                raise ConflictError(_REQUEST_UNAVAILABLE, code="request_unavailable")
            await repository.set_request_status(pending, "rejected")
            await self._audit.record(
                session,
                category="privacy",
                action="contact.request_rejected",
                actor_id=user.id,
                target_type="user",
                target_id=str(pending.from_user_id),
                metadata={"blocked": block},
            )
            if block:
                await self._block(repository, user, pending.from_user_id)

    async def cancel_request(self, user: AuthenticatedUser, request_id: UUID) -> None:
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            pending = await repository.get_request_for_update(request_id)
            if pending is None or pending.from_user_id != user.id:
                raise NotFoundError("Request not found.")
            if pending.status != "pending":
                raise ConflictError(_REQUEST_UNAVAILABLE, code="request_unavailable")
            await repository.set_request_status(pending, "cancelled")
            await self._audit.record(
                session,
                category="privacy",
                action="contact.request_cancelled",
                actor_id=user.id,
                target_type="user",
                target_id=str(pending.to_user_id),
            )

    # -- groups ------------------------------------------------------------------------------

    @staticmethod
    def _group(group: ContactGroup, member_count: int) -> GroupResponse:
        return GroupResponse(
            id=group.id,
            name=group.name,
            color=group.color,
            position=group.position,
            member_count=member_count,
        )

    async def list_groups(self, user: AuthenticatedUser) -> list[GroupResponse]:
        async with self._db.transaction() as session:
            rows = await ContactRepository(session).list_groups(user.id)
        return [self._group(group, count) for group, count in rows]

    async def create_group(self, user: AuthenticatedUser, request: GroupCreate) -> GroupResponse:
        await self._write_limit(user)
        try:
            async with self._db.transaction() as session:
                group = await ContactRepository(session).create_group(
                    user.id, request.name, request.color
                )
        except GroupNameTakenError as exc:
            raise ConflictError(
                "You already have a group with that name.", code="group_name_taken"
            ) from exc
        except GroupLimitReachedError as exc:
            raise UnprocessableError(
                "You can have up to 20 groups.", code="group_limit_reached"
            ) from exc
        return self._group(group, 0)

    async def update_group(
        self, user: AuthenticatedUser, group_id: UUID, request: GroupUpdate
    ) -> GroupResponse:
        await self._write_limit(user)
        changes = request.model_dump(exclude_unset=True)
        try:
            async with self._db.transaction() as session:
                repository = ContactRepository(session)
                group = await repository.get_group(user.id, group_id)
                if group is None:
                    raise NotFoundError("Group not found.")
                if changes:
                    group = await repository.apply_group(group, changes)
                count = await repository.member_count(group.id)
        except GroupNameTakenError as exc:
            raise ConflictError(
                "You already have a group with that name.", code="group_name_taken"
            ) from exc
        return self._group(group, count)

    async def delete_group(self, user: AuthenticatedUser, group_id: UUID) -> None:
        """Deleting a group never deletes its contacts (FR-CONTACTS-005 AC2)."""
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            group = await repository.get_group(user.id, group_id)
            if group is None:
                raise NotFoundError("Group not found.")
            await repository.delete_group(group)

    async def add_group_members(
        self, user: AuthenticatedUser, group_id: UUID, contact_ids: list[UUID]
    ) -> GroupResponse:
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            group = await repository.get_group(user.id, group_id)
            if group is None:
                raise NotFoundError("Group not found.")
            owned = await repository.owned_contact_ids(user.id, contact_ids)
            if owned != set(contact_ids):
                raise NotFoundError("Contact not found.")
            await repository.add_members(user.id, group_id, contact_ids)
            count = await repository.member_count(group_id)
        return self._group(group, count)

    async def remove_group_member(
        self, user: AuthenticatedUser, group_id: UUID, contact_id: UUID
    ) -> None:
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            if await repository.get_group(user.id, group_id) is None:
                raise NotFoundError("Group not found.")
            await repository.remove_member(user.id, group_id, contact_id)

    # -- blocks ------------------------------------------------------------------------------

    @staticmethod
    async def _block(
        repository: ContactRepository, user: AuthenticatedUser, target_id: UUID
    ) -> None:
        await repository.add_block(user.id, target_id)
        # Anything still pending between the two is withdrawn silently.
        await repository.cancel_pending_between(user.id, target_id)

    async def block_user(self, user: AuthenticatedUser, target_id: UUID) -> BlockItem:
        if target_id == user.id:
            raise UnprocessableError(
                "You can't block yourself.",
                details={"problems": [{"field": "body.user_id", "reason": "Not allowed"}]},
            )
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            target = (await repository.profiles_by_ids([target_id])).get(target_id)
            if target is None or target.status in ("deleted",):
                raise NotFoundError("User not found.")
            await self._block(repository, user, target_id)
            await self._audit.record(
                session,
                category="privacy",
                action="contact.blocked",
                actor_id=user.id,
                target_type="user",
                target_id=str(target_id),
            )
            blocks = [b for b in await repository.list_blocks(user.id) if b[1].id == target_id]
        avatars = await self._avatar_urls([blocks[0][1]])
        return BlockItem(
            user_id=target_id,
            person=self._card(blocks[0][1], avatars),
            blocked_at=blocks[0][0].created_at,
        )

    async def unblock_user(self, user: AuthenticatedUser, target_id: UUID) -> None:
        """Unblocking does not re-add a removed contact (FR-CONTACTS-012 AC3)."""
        await self._write_limit(user)
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            if await repository.remove_block(user.id, target_id):
                await self._audit.record(
                    session,
                    category="privacy",
                    action="contact.unblocked",
                    actor_id=user.id,
                    target_type="user",
                    target_id=str(target_id),
                )

    async def list_blocks(self, user: AuthenticatedUser) -> list[BlockItem]:
        async with self._db.transaction() as session:
            rows = await ContactRepository(session).list_blocks(user.id)
        avatars = await self._avatar_urls(profile for _, profile in rows)
        return [
            BlockItem(
                user_id=profile.id, person=self._card(profile, avatars), blocked_at=block.created_at
            )
            for block, profile in rows
        ]

    # -- recent ------------------------------------------------------------------------------

    async def recent_contacts(self, user: AuthenticatedUser) -> list[RecentContact]:
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            conversations = await repository.recent_conversations(user.id, 200)
            other_ids = [c.other_user_id for c in conversations if c.other_user_id is not None]
            by_user = await repository.contact_rows_for_users(user.id, other_ids)

            picked: list[tuple[Contact, Profile, UUID, datetime]] = []
            seen: set[UUID] = set()
            for row in conversations:
                if (
                    row.conversation_type != "chikka"
                    or row.other_user_id is None
                    or row.last_message_at is None
                    or row.other_user_id in seen
                    or row.other_user_id not in by_user
                ):
                    continue
                contact, profile = by_user[row.other_user_id]
                cleared = contact.recent_cleared_at
                if cleared is not None and row.last_message_at <= cleared:
                    continue
                seen.add(row.other_user_id)
                picked.append((contact, profile, row.conversation_id, row.last_message_at))
                if len(picked) == RECENT_LIMIT:
                    break
            enriched, profiles = await self._summaries(
                repository, user.id, [(c, p) for c, p, _, _ in picked]
            )
        avatars = await self._avatar_urls(profiles)
        return [
            RecentContact(
                contact=self._summary(c, p, groups, avatars.get(p.id) if p else None),
                conversation_id=conversation_id,
                last_message_at=at,
            )
            for (c, p, groups), (_, _, conversation_id, at) in zip(enriched, picked, strict=True)
        ]

    async def clear_recent(self, user: AuthenticatedUser) -> None:
        """Hides the recent list. Conversations and messages are untouched."""
        await self._write_limit(user)
        async with self._db.transaction() as session:
            await ContactRepository(session).clear_recent(user.id)

    async def recent_conversations(self, user: AuthenticatedUser) -> list[RecentConversation]:
        async with self._db.transaction() as session:
            repository = ContactRepository(session)
            rows = await repository.recent_conversations(user.id, 100)
            other_ids = [r.other_user_id for r in rows if r.other_user_id is not None]
            hidden = await repository.blocked_user_ids(user.id, other_ids)
            visible_ids = [i for i in other_ids if i not in hidden]
            contacts = await repository.contact_rows_for_users(user.id, visible_ids)
            profiles = await repository.profiles_by_ids(visible_ids)
            phones = [r.remote_phone for r in rows if r.remote_phone]
            sms_contacts = await repository.sms_contacts_by_phone(user.id, phones)

            entries: list[tuple[RecentConversation, Profile | None]] = []
            for row in rows:
                if len(entries) == RECENT_LIMIT:
                    break
                if row.conversation_type == "sms" and row.remote_phone:
                    sms = sms_contacts.get(row.remote_phone)
                    entries.append(
                        (
                            RecentConversation(
                                conversation_id=row.conversation_id,
                                conversation_type="sms",
                                contact_id=sms.id if sms else None,
                                user_id=None,
                                display_name=sms.display_name or "Phone contact"
                                if sms
                                else "Phone contact",
                                avatar_url=None,
                                masked_phone=mask_phone(row.remote_phone),
                                is_contact=sms is not None,
                                last_message_at=row.last_message_at,
                            ),
                            None,
                        )
                    )
                    continue
                other_id = row.other_user_id
                other = profiles.get(other_id) if other_id is not None else None
                if (
                    other_id is None
                    or other is None
                    or other_id in hidden
                    or other.status != "active"
                ):
                    continue
                contact = contacts.get(other_id)
                entries.append(
                    (
                        RecentConversation(
                            conversation_id=row.conversation_id,
                            conversation_type="chikka",
                            contact_id=contact[0].id if contact else None,
                            user_id=other_id,
                            display_name=_display_name(contact[0], other)
                            if contact
                            else other.display_name,
                            avatar_url=None,
                            masked_phone=None,
                            is_contact=contact is not None,
                            last_message_at=row.last_message_at,
                        ),
                        other,
                    )
                )
        avatars = await self._avatar_urls(p for _, p in entries if p is not None)
        return [
            entry.model_copy(update={"avatar_url": avatars.get(p.id) if p else None})
            for entry, p in entries
        ]
