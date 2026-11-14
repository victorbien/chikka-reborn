"""Chikka-to-Chikka messaging (FR-MSG-001, 002, 003, 004, 006, 007, 008, 009, 010, 012, 013).

Message lifecycle (server side):

    sent       stored in the database (the only proof the message exists)
    delivered  the recipient's app received it: a WebSocket ack, or the recipient loading the
               conversation over REST. Pushing a frame is NOT proof of anything.
    read       the recipient viewed it, recorded only when both people allow read receipts

"pending" (not stored yet) and "failed" (could not be stored) live only on the sender's device,
which keeps the client_message_id and retries with it, so a retry never creates a duplicate.

Every change is committed first and pushed to WebSocket clients afterwards. A push that never
arrives is repaired by the client's REST sync, so it can be lost without losing a message.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from starlette.concurrency import run_in_threadpool

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    UnprocessableError,
)
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.integrations.storage_provider import StorageError, StorageProvider
from app.modules.chat.attachments import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    InvalidAttachmentError,
    check_attachment,
    safe_file_name,
)
from app.modules.chat.context import ContextLine, ConversationAiContext
from app.modules.chat.models import Message, MessageAttachment
from app.modules.chat.repository import (
    ChatRepository,
    ConversationRow,
    DeliveryInfo,
    DuplicateMessageError,
    NotAMemberError,
)
from app.modules.chat.schemas import (
    AttachmentOut,
    ChatMessageStatus,
    ConversationPresence,
    ConversationSummary,
    LastMessage,
    MessageOut,
    MessagePage,
    Participant,
    ReadState,
    SendMessageRequest,
    StatusChange,
    UnreadTotals,
)
from app.modules.contacts.directory import ContactDirectory, Relationship
from app.modules.notifications.service import create_notification
from app.modules.profiles.models import Profile
from app.modules.profiles.presence import PresenceRegistry
from app.modules.profiles.schemas import PresencePreference
from app.modules.rate_limits import service as limits
from app.modules.rate_limits.service import RateLimiter
from app.realtime.hub import RealtimeHub, event

logger = logging.getLogger(__name__)

URL_TTL_SECONDS = 3600
PREVIEW_CHARS = 120
DEFAULT_PAGE = 50
MAX_PAGE = 100

_NOT_FOUND = "Conversation not found."
_NOT_A_CONTACT = "You can only message your contacts."


def _request_hash(request: SendMessageRequest) -> str:
    payload = json.dumps(
        {"body": request.body or "", "attachments": sorted(str(a) for a in request.attachment_ids)},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _preview(body: str | None, attachment_count: int, deleted: bool) -> str:
    if deleted:
        return "Message deleted"
    if body:
        return body if len(body) <= PREVIEW_CHARS else body[: PREVIEW_CHARS - 1] + "…"
    return "Photo or file" if attachment_count == 1 else f"{attachment_count} files"


class ChatService:
    def __init__(
        self,
        *,
        database: Database,
        attachments: StorageProvider,
        avatars: StorageProvider,
        limiter: RateLimiter,
        presence: PresenceRegistry,
        hub: RealtimeHub,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._db = database
        self._attachments = attachments
        self._avatars = avatars
        self._limiter = limiter
        self._presence = presence
        self._hub = hub
        self._clock = clock

    # -- helpers ---------------------------------------------------------------------------

    @staticmethod
    async def _sign(storage: StorageProvider, path: str | None) -> str | None:
        if not path:
            return None
        try:
            return await storage.signed_url(path, URL_TTL_SECONDS)
        except StorageError:
            return None

    async def _member_or_404(
        self, repository: ChatRepository, conversation_id: UUID, user_id: UUID
    ) -> None:
        # A conversation you are not in looks exactly like one that does not exist.
        if await repository.membership(conversation_id, user_id) is None:
            raise NotFoundError(_NOT_FOUND)

    def _presence_for(self, profile: Profile, relationship: Relationship) -> ConversationPresence:
        if relationship.they_blocked or profile.share_presence == "nobody":
            return "unknown"
        if profile.share_presence == "contacts" and not relationship.is_contact:
            return "unknown"
        live = self._presence.status(
            str(profile.id), cast(PresencePreference, profile.presence_preference)
        )
        seen = self._presence.as_seen_by_others(live)
        return "offline" if seen == "invisible" else cast(ConversationPresence, seen)

    @staticmethod
    def _can_send(relationship: Relationship, profile: Profile) -> tuple[bool, str | None]:
        if relationship.i_blocked:
            return False, "You blocked this person. Unblock them to send messages."
        if not relationship.is_contact:
            return False, "You are no longer contacts. Send a contact request to message again."
        if profile.status != "active":
            return False, "This person can't receive messages right now."
        # Blocked by them: allowed, silently (FR-PRIVACY-006). Never disclosed.
        return True, None

    async def _summaries(
        self,
        session_repository: ChatRepository,
        directory: ContactDirectory,
        viewer: UUID,
        rows: list[ConversationRow],
    ) -> list[ConversationSummary]:
        others = [row.other_user_id for row in rows]
        profiles = await session_repository.profiles(others)
        relationships = await directory.relationships(viewer, others)
        avatars = await asyncio.gather(
            *(
                self._sign(self._avatars, profiles[o].avatar_path if o in profiles else None)
                for o in others
            )
        )
        summaries: list[ConversationSummary] = []
        for row, avatar in zip(rows, avatars, strict=True):
            profile = profiles.get(row.other_user_id)
            if profile is None:
                continue
            relationship = relationships[row.other_user_id]
            can_send, reason = self._can_send(relationship, profile)
            last = None
            if (
                row.last_id is not None
                and row.last_seq is not None
                and row.last_created_at is not None
            ):
                mine = row.last_sender == viewer
                last = LastMessage(
                    id=row.last_id,
                    seq=row.last_seq,
                    is_mine=mine,
                    preview=_preview(
                        row.last_body, row.last_attachment_count or 0, row.last_deleted
                    ),
                    has_attachments=bool(row.last_attachment_count),
                    created_at=row.last_created_at,
                    status=cast(ChatMessageStatus, row.last_status) if mine else None,
                )
            summaries.append(
                ConversationSummary(
                    id=row.id,
                    conversation_type="chikka",
                    participant=Participant(
                        user_id=profile.id,
                        username=profile.username,
                        display_name=profile.display_name,
                        avatar_url=avatar,
                        presence=self._presence_for(profile, relationship),
                        is_contact=relationship.is_contact,
                    ),
                    last_message=last,
                    last_message_at=row.last_message_at,
                    unread_count=row.unread_count,
                    is_archived=row.is_archived,
                    is_muted=row.is_muted,
                    can_send=can_send,
                    cannot_send_reason=reason,
                )
            )
        return summaries

    async def _render(
        self,
        repository: ChatRepository,
        messages: Sequence[Message],
        viewers: Iterable[UUID],
    ) -> dict[UUID, list[MessageOut]]:
        """Each viewer's view of the messages, as the REST API returns them."""
        ids = [m.id for m in messages]
        attachments = await repository.attachments_for(ids)
        deliveries = await repository.deliveries(ids)
        flat = [a for group in attachments.values() for a in group]
        urls = await asyncio.gather(*(self._sign(self._attachments, a.storage_path) for a in flat))
        url_by_id = {a.id: url for a, url in zip(flat, urls, strict=True)}

        views: dict[UUID, list[MessageOut]] = {}
        for viewer in viewers:
            rendered: list[MessageOut] = []
            for message in messages:
                sender = message.sender_user_id
                if sender is None:
                    continue
                mine = sender == viewer
                delivery: DeliveryInfo | None = deliveries.get(message.id)
                deleted = message.deleted_for_everyone_at is not None
                out = MessageOut(
                    id=message.id,
                    conversation_id=message.conversation_id,
                    seq=message.seq,
                    sender_user_id=sender,
                    is_mine=mine,
                    body=None if deleted else message.body,
                    attachments=[]
                    if deleted
                    else [
                        AttachmentOut(
                            id=a.id,
                            file_name=a.file_name,
                            content_type=a.content_type,
                            size_bytes=a.size_bytes,
                            url=url_by_id.get(a.id),
                        )
                        for a in attachments.get(message.id, [])
                    ],
                    created_at=message.created_at,
                    edited_at=message.edited_at,
                )
                if mine:
                    # A suppressed (blocked) message has no delivery row and stays "sent".
                    out.client_message_id = message.idempotency_key
                    out.status = cast(ChatMessageStatus, message.status)
                    out.status_version = message.status_version
                    out.delivered_at = delivery.delivered_at if delivery else None
                    out.read_at = delivery.read_at if delivery else None
                rendered.append(out)
            views[viewer] = rendered
        return views

    async def _status_changes(
        self, repository: ChatRepository, message_ids: Sequence[UUID]
    ) -> dict[UUID, list[StatusChange]]:
        """Changes grouped by the sender who should hear about them."""
        if not message_ids:
            return {}
        messages = await repository.messages_by_ids(message_ids)
        for message in messages:
            await repository.refresh_message(message)  # status_version is set by a trigger
        deliveries = await repository.deliveries(message_ids)
        grouped: dict[UUID, list[StatusChange]] = {}
        for message in messages:
            delivery = deliveries.get(message.id)
            if message.sender_user_id is None:
                continue
            grouped.setdefault(message.sender_user_id, []).append(
                StatusChange(
                    message_id=message.id,
                    conversation_id=message.conversation_id,
                    status=cast(ChatMessageStatus, message.status),
                    status_version=message.status_version,
                    delivered_at=delivery.delivered_at if delivery else None,
                    read_at=delivery.read_at if delivery else None,
                )
            )
        return grouped

    def _publish_status(self, changes: dict[UUID, list[StatusChange]]) -> None:
        for sender, items in changes.items():
            for change in items:
                self._hub.publish(
                    [sender],
                    event(
                        "message.status_changed",
                        change.model_dump(mode="json"),
                        conversation_id=change.conversation_id,
                    ),
                )

    async def _receipts_enabled(self, repository: ChatRepository, a: UUID, b: UUID | None) -> bool:
        if b is None:
            return False
        profiles = await repository.profiles([a, b])
        return all(p.send_read_receipts for p in profiles.values()) and len(profiles) == 2

    # -- conversations ---------------------------------------------------------------------

    async def open_conversation(
        self, user: AuthenticatedUser, other_id: UUID
    ) -> ConversationSummary:
        """The single conversation with a contact, created on first use (FR-MSG-013)."""
        if other_id == user.id:
            raise UnprocessableError(
                "You can't start a conversation with yourself.",
                details={"problems": [{"field": "body.user_id", "reason": "Not allowed"}]},
            )
        await self._limiter.hit(limits.CHAT_WRITE_PER_USER, str(user.id))
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            directory = ContactDirectory(session)
            relationship = await directory.relationship(user.id, other_id)
            profiles = await repository.profiles([other_id])
            other = profiles.get(other_id)
            # One neutral answer for "not a contact", "unknown user" and "you blocked them".
            if other is None or not relationship.is_contact or relationship.i_blocked:
                raise PermissionDeniedError(_NOT_A_CONTACT, code="not_a_contact")
            if other.status != "active":
                raise PermissionDeniedError(
                    "This person can't receive messages right now.", code="recipient_unavailable"
                )
            conversation_id = await repository.get_or_create_chikka(user.id, other_id)
            row = await repository.conversation(user.id, conversation_id)
            if row is None:  # pragma: no cover - just created inside this transaction
                raise NotFoundError(_NOT_FOUND)
            return (await self._summaries(repository, directory, user.id, [row]))[0]

    async def list_conversations(
        self,
        user: AuthenticatedUser,
        *,
        archived: bool,
        query: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ConversationSummary], int]:
        term = (query or "").strip() or None
        if term is not None:
            if not 2 <= len(term) <= 100:
                raise UnprocessableError(
                    "Search with 2 to 100 characters.",
                    code="query_length",
                    details={"problems": [{"field": "query.q", "reason": "Length"}]},
                )
            await self._limiter.hit(limits.CHAT_SEARCH_PER_USER, str(user.id))
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            directory = ContactDirectory(session)
            hidden = await directory.blocked_by_me(user.id)
            rows, total = await repository.conversations(
                user.id,
                # A search looks through archived conversations too.
                archived=None if term else archived,
                query=term,
                hidden_users=hidden,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
            return await self._summaries(repository, directory, user.id, rows), total

    async def get_conversation(
        self, user: AuthenticatedUser, conversation_id: UUID
    ) -> ConversationSummary:
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            row = await repository.conversation(user.id, conversation_id)
            if row is None:
                raise NotFoundError(_NOT_FOUND)
            return (await self._summaries(repository, ContactDirectory(session), user.id, [row]))[0]

    async def set_archived(
        self, user: AuthenticatedUser, conversation_id: UUID, archived: bool
    ) -> ConversationSummary:
        await self._limiter.hit(limits.CHAT_WRITE_PER_USER, str(user.id))
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            await self._member_or_404(repository, conversation_id, user.id)
            await repository.set_archived(conversation_id, user.id, archived)
        summary = await self.get_conversation(user, conversation_id)
        # Other tabs and devices of the same user update their lists.
        self._hub.publish(
            [user.id],
            event(
                "conversation.updated", {"is_archived": archived}, conversation_id=conversation_id
            ),
        )
        return summary

    async def unread_totals(self, user: AuthenticatedUser) -> UnreadTotals:
        async with self._db.transaction() as session:
            hidden = await ContactDirectory(session).blocked_by_me(user.id)
            messages, threads = await ChatRepository(session).unread_totals(user.id, hidden)
        return UnreadTotals(unread_messages=messages, unread_conversations=threads)

    # -- messages --------------------------------------------------------------------------

    async def ai_context(
        self, user: AuthenticatedUser, conversation_id: UUID, limit: int
    ) -> ConversationAiContext:
        """Recent text messages for the AI assistant, oldest first. Members only (else 404)."""
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            await self._member_or_404(repository, conversation_id, user.id)
            if not await repository.ai_enabled_for(conversation_id, user.id):
                return ConversationAiContext(ai_enabled=False, lines=[])
            rows = await repository.recent_text(user.id, conversation_id, limit)
        lines = [ContextLine(from_me=sender == user.id, text=body) for sender, body in rows]
        return ConversationAiContext(ai_enabled=True, lines=list(reversed(lines)))

    async def list_messages(
        self,
        user: AuthenticatedUser,
        conversation_id: UUID,
        *,
        before_seq: int | None,
        after_seq: int | None,
        limit: int,
    ) -> MessagePage:
        if before_seq is not None and after_seq is not None:
            raise UnprocessableError("Use before_seq or after_seq, not both.", code="bad_cursor")
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            await self._member_or_404(repository, conversation_id, user.id)
            messages, more = await repository.messages(
                user.id, conversation_id, before_seq=before_seq, after_seq=after_seq, limit=limit
            )
            # The recipient's app now holds these messages: that is what "delivered" means.
            incoming = [m.id for m in messages if m.sender_user_id != user.id]
            changed = await repository.mark_delivered(user.id, message_ids=incoming)
            changes = await self._status_changes(repository, changed)
            other = await repository.other_member(conversation_id, user.id)
            peer_read = (
                await repository.last_read_seq(conversation_id, other)
                if other is not None and await self._receipts_enabled(repository, user.id, other)
                else None
            )
            views = await self._render(repository, messages, [user.id])
            last_read = await repository.last_read_seq(conversation_id, user.id)
        self._publish_status(changes)
        return MessagePage(
            messages=views[user.id],
            has_more_before=more,
            last_read_seq=last_read,
            peer_read_seq=peer_read,
        )

    async def send_message(
        self, user: AuthenticatedUser, conversation_id: UUID, request: SendMessageRequest
    ) -> tuple[MessageOut, bool]:
        """Store a message once. Returns (message, created). A repeated client_message_id
        returns the original message (created=False) and is never stored or pushed twice."""
        if len(request.attachment_ids) > MAX_ATTACHMENTS_PER_MESSAGE:
            raise UnprocessableError("You can attach up to 5 files.", code="too_many_attachments")
        request_hash = _request_hash(request)

        # A retry of a stored message is answered before the rate limit, so retrying after a
        # network drop never counts twice.
        existing = await self._existing(
            user, conversation_id, request.client_message_id, request_hash
        )
        if existing is not None:
            return existing, False

        await self._limiter.hit(limits.MESSAGE_SEND_PER_USER, str(user.id))
        now = self._clock()
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            await self._member_or_404(repository, conversation_id, user.id)
            other = await repository.other_member(conversation_id, user.id)
            if other is None:  # pragma: no cover - chikka conversations always have two members
                raise NotFoundError(_NOT_FOUND)
            relationship = await ContactDirectory(session).relationship(user.id, other)
            recipient = (await repository.profiles([other])).get(other)
            if recipient is None:  # pragma: no cover
                raise NotFoundError(_NOT_FOUND)
            allowed, reason = self._can_send(relationship, recipient)
            if not allowed:
                code = "user_blocked" if relationship.i_blocked else "cannot_send"
                raise PermissionDeniedError(reason or _NOT_A_CONTACT, code=code)

            files = await repository.pending_attachments(
                user.id, conversation_id, request.attachment_ids
            )
            if len(files) != len(request.attachment_ids):
                raise UnprocessableError(
                    "One of the attachments is no longer available. Remove it and try again.",
                    code="attachment_unavailable",
                )

            # They blocked you: the message is stored for you only and never reaches them.
            suppressed = relationship.they_blocked
            message = Message(
                conversation_id=conversation_id,
                channel="chikka",
                direction="outbound",
                sender_user_id=user.id,
                body=request.body,
                status="sent",
                idempotency_key=request.client_message_id,
                request_hash=request_hash,
                attachment_count=len(files),
                suppressed_at=now if suppressed else None,
                suppressed_reason="blocked" if suppressed else None,
            )
            try:
                message = await repository.insert_message(message)
            except DuplicateMessageError:
                duplicate = await repository.find_by_client_id(user.id, request.client_message_id)
                if duplicate is None:  # pragma: no cover
                    raise
                return await self._resolve_duplicate(
                    repository, duplicate, conversation_id, request_hash, user.id
                ), False
            except NotAMemberError as exc:
                raise NotFoundError(_NOT_FOUND) from exc

            if files:
                await repository.link_attachments([f.id for f in files], message.id)
            if not suppressed:
                await repository.insert_delivery(message.id, other, now)
                await repository.unarchive_unmuted(conversation_id)
                if not await repository.is_muted(conversation_id, other):
                    sender = (await repository.profiles([user.id])).get(user.id)
                    # Several unread messages from one chat fold into one notification.
                    await create_notification(
                        session,
                        user_id=other,
                        notification_type="new_message",
                        title=f"New message from {sender.display_name if sender else 'someone'}",
                        body=(request.body or "Sent an attachment")[:120],
                        reference_type="conversation",
                        reference_id=conversation_id,
                        group_key=f"chat:{conversation_id}",
                        dedupe_key=f"chat_message:{message.id}",
                        now=now,
                    )
            else:
                await repository.set_archived(conversation_id, user.id, False)
            message = await repository.refresh_message(message)
            audience = [user.id] if suppressed else [user.id, other]
            views = await self._render(repository, [message], audience)

        self._hub.publish_each(
            {
                viewer: event(
                    "message.created",
                    {"message": items[0].model_dump(mode="json")},
                    conversation_id=conversation_id,
                )
                for viewer, items in views.items()
            }
        )
        return views[user.id][0], True

    async def _existing(
        self,
        user: AuthenticatedUser,
        conversation_id: UUID,
        client_message_id: UUID,
        request_hash: str,
    ) -> MessageOut | None:
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            found = await repository.find_by_client_id(user.id, client_message_id)
            if found is None:
                return None
            return await self._resolve_duplicate(
                repository, found, conversation_id, request_hash, user.id
            )

    async def _resolve_duplicate(
        self,
        repository: ChatRepository,
        found: Message,
        conversation_id: UUID,
        request_hash: str,
        viewer: UUID,
    ) -> MessageOut:
        if found.conversation_id != conversation_id or found.request_hash != request_hash:
            raise ConflictError(
                "This message ID was already used for a different message.",
                code="idempotency_conflict",
            )
        return (await self._render(repository, [found], [viewer]))[viewer][0]

    async def acknowledge(self, user: AuthenticatedUser, message_ids: Sequence[UUID]) -> int:
        """The recipient's app received these messages (WebSocket `ack`). Only the caller's own
        deliveries can change, so ids of other people's messages are ignored."""
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            changed = await repository.mark_delivered(user.id, message_ids=list(message_ids))
            changes = await self._status_changes(repository, changed)
        self._publish_status(changes)
        return len(changed)

    async def mark_read(
        self, user: AuthenticatedUser, conversation_id: UUID, up_to_seq: int
    ) -> ReadState:
        """Unread counts clear whether or not read receipts are on (FR-MSG-008 AC2)."""
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            await self._member_or_404(repository, conversation_id, user.id)
            last_read = await repository.advance_read(conversation_id, user.id, up_to_seq)
            other = await repository.other_member(conversation_id, user.id)
            if await self._receipts_enabled(repository, user.id, other):
                changed = await repository.mark_read_receipts(user.id, conversation_id, last_read)
            else:
                # Seen without receipts still proves the app received them.
                changed = await repository.mark_delivered(
                    user.id, conversation_id=conversation_id, up_to_seq=last_read
                )
            changes = await self._status_changes(repository, changed)
            unread = await repository.unread_count(user.id, conversation_id)
        self._publish_status(changes)
        state = ReadState(
            conversation_id=conversation_id, last_read_seq=last_read, unread_count=unread
        )
        self._hub.publish(
            [user.id],
            event(
                "conversation.read", state.model_dump(mode="json"), conversation_id=conversation_id
            ),
        )
        return state

    async def typing(self, user: AuthenticatedUser, conversation_id: UUID) -> bool:
        """Ephemeral, never stored (FR-MSG-003). Silent when anything would make it a leak."""
        async with self._db.transaction() as session:
            repository = ChatRepository(session)
            if await repository.membership(conversation_id, user.id) is None:
                raise NotFoundError(_NOT_FOUND)
            other = await repository.other_member(conversation_id, user.id)
            if other is None:
                return False
            sender = (await repository.profiles([user.id])).get(user.id)
            relationship = await ContactDirectory(session).relationship(user.id, other)
        if (
            sender is None
            or not sender.send_typing_indicators
            or not relationship.is_contact
            or relationship.blocked_either_way
        ):
            return False
        self._hub.publish(
            [other],
            event("typing", {"user_id": str(user.id)}, conversation_id=conversation_id),
        )
        return True

    # -- attachments -----------------------------------------------------------------------

    async def upload_attachment(
        self, user: AuthenticatedUser, conversation_id: UUID, file_name: str | None, data: bytes
    ) -> AttachmentOut:
        await self._limiter.hit(limits.ATTACHMENT_UPLOAD_PER_USER, str(user.id))
        async with self._db.transaction() as session:
            await self._member_or_404(ChatRepository(session), conversation_id, user.id)
        try:
            checked = await run_in_threadpool(check_attachment, data)
        except InvalidAttachmentError as exc:
            raise UnprocessableError(
                exc.reason,
                code="invalid_attachment",
                details={"problems": [{"field": "file", "reason": exc.reason}]},
            ) from exc

        path = f"{conversation_id}/{uuid.uuid4().hex}{checked.extension}"
        try:
            await self._attachments.upload(path, checked.data, checked.content_type)
        except StorageError as exc:
            raise ServiceUnavailableError(
                "File upload is unavailable right now. Please try again.",
                code="storage_unavailable",
            ) from exc
        try:
            async with self._db.transaction() as session:
                attachment = await ChatRepository(session).add_attachment(
                    MessageAttachment(
                        conversation_id=conversation_id,
                        uploader_id=user.id,
                        storage_path=path,
                        file_name=safe_file_name(file_name, checked.content_type),
                        content_type=checked.content_type,
                        size_bytes=len(checked.data),
                    )
                )
        except Exception:
            # Do not leave an unreferenced file behind.
            try:
                await self._attachments.delete(path)
            except StorageError:
                logger.warning("orphaned attachment not deleted")
            raise
        return AttachmentOut(
            id=attachment.id,
            file_name=attachment.file_name,
            content_type=attachment.content_type,
            size_bytes=attachment.size_bytes,
            url=await self._sign(self._attachments, path),
        )
