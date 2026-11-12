"""Database access for Module C. Every read takes the viewer and applies the same visibility
rules as the messages RLS policy: membership, "cleared" history, per-user hides and blocked
(suppressed) messages, which only their sender sees. The service owns the transaction."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import (
    Conversation,
    ConversationMember,
    Message,
    MessageAttachment,
    MessageDelivery,
)
from app.modules.profiles.models import Profile


class DuplicateMessageError(Exception):
    """The (sender, client_message_id) pair already exists."""


class NotAMemberError(Exception):
    """The database refused the insert because the sender left or never joined."""


def _sqlstate(exc: IntegrityError) -> str | None:
    original = exc.orig
    return getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)


# What a viewer may see of a message, as SQL over `m` (messages) and `cm` (their membership).
_VISIBLE = """
    m.seq > cm.cleared_before_seq
    and (m.suppressed_at is null or m.sender_user_id = :viewer)
    and not exists (
        select 1 from public.message_hides h where h.message_id = m.id and h.user_id = :viewer)
"""

_UNREAD = f"""
    (select count(*) from public.messages m
      where m.conversation_id = cm.conversation_id
        and m.seq > greatest(cm.last_read_seq, cm.cleared_before_seq)
        and m.sender_user_id <> :viewer
        and m.deleted_for_everyone_at is null
        and {_VISIBLE})
"""


@dataclass(frozen=True)
class ConversationRow:
    id: UUID
    last_message_at: datetime | None
    last_read_seq: int
    is_archived: bool
    is_muted: bool
    unread_count: int
    other_user_id: UUID
    last_id: UUID | None
    last_seq: int | None
    last_body: str | None
    last_sender: UUID | None
    last_attachment_count: int | None
    last_created_at: datetime | None
    last_status: str | None
    last_deleted: bool


@dataclass(frozen=True)
class DeliveryInfo:
    status: str
    delivered_at: datetime | None
    read_at: datetime | None


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- conversations ---------------------------------------------------------------------

    async def get_or_create_chikka(self, user_a: UUID, user_b: UUID) -> UUID:
        result = await self._session.execute(
            text("select private.get_or_create_chikka_conversation(:a, :b)"),
            {"a": user_a, "b": user_b},
        )
        return UUID(str(result.scalar_one()))

    async def membership(self, conversation_id: UUID, user_id: UUID) -> ConversationMember | None:
        """The caller's active membership of a chikka conversation, or None."""
        statement = (
            select(ConversationMember)
            .join(Conversation, Conversation.id == ConversationMember.conversation_id)
            .where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id,
                ConversationMember.left_at.is_(None),
                Conversation.conversation_type == "chikka",
            )
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def other_member(self, conversation_id: UUID, user_id: UUID) -> UUID | None:
        statement = select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id != user_id,
        )
        return (await self._session.execute(statement)).scalars().first()

    async def active_member_ids(self, conversation_id: UUID) -> list[UUID]:
        statement = select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.left_at.is_(None),
        )
        return list((await self._session.execute(statement)).scalars())

    async def set_archived(self, conversation_id: UUID, user_id: UUID, archived: bool) -> None:
        await self._session.execute(
            update(ConversationMember)
            .where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id,
            )
            .values(is_archived=archived)
        )

    async def unarchive_unmuted(self, conversation_id: UUID) -> None:
        """A new message brings an archived conversation back, unless it is muted."""
        now = datetime.now(UTC)
        await self._session.execute(
            update(ConversationMember)
            .where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.is_archived.is_(True),
                ConversationMember.muted_indefinitely.is_(False),
                or_(
                    ConversationMember.muted_until.is_(None), ConversationMember.muted_until <= now
                ),
            )
            .values(is_archived=False)
        )

    def _summary_sql(self, conditions: list[str], *, count_only: bool = False) -> str:
        where = " and ".join(["true", *conditions])
        if count_only:
            return f"""
                select count(*) from public.conversation_members cm
                join public.conversations c on c.id = cm.conversation_id
                join public.conversation_members other
                  on other.conversation_id = c.id and other.user_id <> :viewer
                join public.profiles p on p.id = other.user_id
                where cm.user_id = :viewer and cm.left_at is null
                  and c.conversation_type = 'chikka' and {where}
            """
        return f"""
            select c.id, c.last_message_at, cm.last_read_seq, cm.is_archived,
                   (cm.muted_indefinitely or coalesce(cm.muted_until > now(), false)) as is_muted,
                   {_UNREAD} as unread_count,
                   other.user_id as other_user_id,
                   lm.id as last_id, lm.seq as last_seq, lm.body as last_body,
                   lm.sender_user_id as last_sender, lm.attachment_count as last_attachment_count,
                   lm.created_at as last_created_at, lm.status as last_status,
                   coalesce(lm.deleted_for_everyone_at is not null, false) as last_deleted
            from public.conversation_members cm
            join public.conversations c on c.id = cm.conversation_id
            join public.conversation_members other
              on other.conversation_id = c.id and other.user_id <> :viewer
            join public.profiles p on p.id = other.user_id
            left join lateral (
                select m.id, m.seq, m.body, m.sender_user_id, m.attachment_count, m.created_at,
                       m.status, m.deleted_for_everyone_at
                from public.messages m
                where m.conversation_id = c.id and {_VISIBLE}
                order by m.seq desc
                limit 1
            ) lm on true
            where cm.user_id = :viewer and cm.left_at is null
              and c.conversation_type = 'chikka' and {where}
            order by cm.is_pinned desc, c.last_message_at desc nulls last, c.id
        """

    @staticmethod
    def _filters(
        *,
        archived: bool | None,
        query: str | None,
        hidden_users: set[UUID],
        conversation_id: UUID | None,
        params: dict[str, Any],
    ) -> list[str]:
        conditions: list[str] = []
        if conversation_id is not None:
            conditions.append("c.id = :conversation_id")
            params["conversation_id"] = conversation_id
        else:
            # A thread nobody has written in yet is not listed (it is still reachable by id).
            conditions.append("c.last_message_at is not null")
        if archived is not None:
            conditions.append("cm.is_archived = :archived")
            params["archived"] = archived
        if hidden_users:
            conditions.append("not (other.user_id = any(:hidden_users))")
            params["hidden_users"] = list(hidden_users)
        if query:
            params["pattern"] = (
                f"%{query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')}%"
            )
            params["query"] = query
            conditions.append(
                f"""(p.display_name ilike :pattern or p.username ilike :pattern
                     or exists (select 1 from public.messages m
                                where m.conversation_id = c.id
                                  and m.deleted_for_everyone_at is null
                                  and {_VISIBLE}
                                  and m.search_vector @@ plainto_tsquery('simple', :query)))"""
            )
        return conditions

    async def conversations(
        self,
        viewer: UUID,
        *,
        archived: bool | None,
        query: str | None,
        hidden_users: set[UUID],
        offset: int,
        limit: int,
    ) -> tuple[list[ConversationRow], int]:
        params: dict[str, Any] = {"viewer": viewer}
        conditions = self._filters(
            archived=archived,
            query=query,
            hidden_users=hidden_users,
            conversation_id=None,
            params=params,
        )
        total = (
            await self._session.execute(
                text(self._summary_sql(conditions, count_only=True)), params
            )
        ).scalar_one()
        rows = await self._session.execute(
            text(self._summary_sql(conditions) + " limit :limit offset :offset"),
            {**params, "limit": limit, "offset": offset},
        )
        return [ConversationRow(**row._mapping) for row in rows], int(total)

    async def conversation(self, viewer: UUID, conversation_id: UUID) -> ConversationRow | None:
        params: dict[str, Any] = {"viewer": viewer}
        conditions = self._filters(
            archived=None,
            query=None,
            hidden_users=set(),
            conversation_id=conversation_id,
            params=params,
        )
        row = (await self._session.execute(text(self._summary_sql(conditions)), params)).first()
        return None if row is None else ConversationRow(**row._mapping)

    async def unread_totals(self, viewer: UUID, hidden_users: set[UUID]) -> tuple[int, int]:
        params: dict[str, Any] = {"viewer": viewer}
        hidden = ""
        if hidden_users:
            hidden = "and not (other.user_id = any(:hidden_users))"
            params["hidden_users"] = list(hidden_users)
        row = (
            await self._session.execute(
                text(
                    f"""
                    select coalesce(sum(n), 0) as messages, count(*) filter (where n > 0) as threads
                    from (
                        select {_UNREAD} as n
                        from public.conversation_members cm
                        join public.conversations c on c.id = cm.conversation_id
                        join public.conversation_members other
                          on other.conversation_id = c.id and other.user_id <> :viewer
                        where cm.user_id = :viewer and cm.left_at is null
                          and c.conversation_type = 'chikka'
                          and not cm.muted_indefinitely
                          and coalesce(cm.muted_until <= now(), true)
                          {hidden}
                    ) counts
                    """
                ),
                params,
            )
        ).one()
        return int(row.messages), int(row.threads)

    async def unread_count(self, viewer: UUID, conversation_id: UUID) -> int:
        result = await self._session.execute(
            text(
                f"""select {_UNREAD} from public.conversation_members cm
                    where cm.conversation_id = :conversation_id and cm.user_id = :viewer"""
            ),
            {"viewer": viewer, "conversation_id": conversation_id},
        )
        return int(result.scalar_one())

    # -- messages --------------------------------------------------------------------------

    async def find_by_client_id(self, sender: UUID, client_message_id: UUID) -> Message | None:
        statement = select(Message).where(
            Message.sender_user_id == sender, Message.idempotency_key == client_message_id
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def insert_message(self, message: Message) -> Message:
        self._session.add(message)
        try:
            async with self._session.begin_nested():
                await self._session.flush()
        except IntegrityError as exc:
            self._session.expunge(message)
            if _sqlstate(exc) == "23505":
                raise DuplicateMessageError from exc
            raise
        except Exception as exc:
            self._session.expunge(message)
            if "NOT_A_MEMBER" in str(exc):
                raise NotAMemberError from exc
            raise
        await self._session.refresh(message)
        return message

    async def insert_delivery(self, message_id: UUID, recipient: UUID, now: datetime) -> None:
        self._session.add(
            MessageDelivery(
                message_id=message_id,
                channel="chikka",
                recipient_user_id=recipient,
                status="sent",
                sent_at=now,
            )
        )
        await self._session.flush()

    async def messages(
        self,
        viewer: UUID,
        conversation_id: UUID,
        *,
        before_seq: int | None,
        after_seq: int | None,
        limit: int,
    ) -> tuple[list[Message], bool]:
        """Up to `limit` visible messages in ascending seq order, plus whether older ones exist."""
        params: dict[str, Any] = {"viewer": viewer, "conversation_id": conversation_id}
        bound = ""
        if after_seq is not None:
            bound = "and m.seq > :after_seq"
            params["after_seq"] = after_seq
            order = "asc"
        else:
            order = "desc"
            if before_seq is not None:
                bound = "and m.seq < :before_seq"
                params["before_seq"] = before_seq
        ids_sql = text(
            f"""
            select m.id from public.messages m
            join public.conversation_members cm
              on cm.conversation_id = m.conversation_id and cm.user_id = :viewer
            where m.conversation_id = :conversation_id and {_VISIBLE} {bound}
            order by m.seq {order}
            limit :limit
            """
        )
        ids = list((await self._session.execute(ids_sql, {**params, "limit": limit + 1})).scalars())
        more = len(ids) > limit
        ids = ids[:limit]
        if not ids:
            return [], False
        rows = (
            await self._session.execute(
                select(Message).where(Message.id.in_(ids)).order_by(Message.seq)
            )
        ).scalars()
        messages = list(rows)
        # "More before" only applies when paging backwards; forward sync fetches until empty.
        return messages, more if after_seq is None else False

    async def message_for_viewer(self, viewer: UUID, message_id: UUID) -> Message | None:
        statement = text(
            f"""
            select m.id from public.messages m
            join public.conversation_members cm
              on cm.conversation_id = m.conversation_id and cm.user_id = :viewer
                 and cm.left_at is null
            where m.id = :message_id and {_VISIBLE}
            """
        )
        found = (
            await self._session.execute(statement, {"viewer": viewer, "message_id": message_id})
        ).scalar_one_or_none()
        if found is None:
            return None
        return await self._session.get(Message, found)

    async def refresh_message(self, message: Message) -> Message:
        await self._session.refresh(message)
        return message

    async def deliveries(self, message_ids: Sequence[UUID]) -> dict[UUID, DeliveryInfo]:
        if not message_ids:
            return {}
        statement = select(
            MessageDelivery.message_id,
            MessageDelivery.status,
            MessageDelivery.delivered_at,
            MessageDelivery.read_at,
        ).where(
            MessageDelivery.message_id.in_(set(message_ids)), MessageDelivery.channel == "chikka"
        )
        return {
            row.message_id: DeliveryInfo(row.status, row.delivered_at, row.read_at)
            for row in await self._session.execute(statement)
        }

    async def mark_delivered(
        self,
        recipient: UUID,
        *,
        message_ids: Sequence[UUID] | None = None,
        conversation_id: UUID | None = None,
        up_to_seq: int | None = None,
    ) -> list[UUID]:
        """Move this recipient's 'sent' deliveries to 'delivered'. Returns changed message ids."""
        now = datetime.now(UTC)
        statement = (
            update(MessageDelivery)
            .where(
                MessageDelivery.recipient_user_id == recipient,
                MessageDelivery.channel == "chikka",
                MessageDelivery.status == "sent",
            )
            .values(status="delivered", delivered_at=now)
            .returning(MessageDelivery.message_id)
        )
        if message_ids is not None:
            if not message_ids:
                return []
            statement = statement.where(MessageDelivery.message_id.in_(set(message_ids)))
        if conversation_id is not None:
            subquery = select(Message.id).where(Message.conversation_id == conversation_id)
            if up_to_seq is not None:
                subquery = subquery.where(Message.seq <= up_to_seq)
            statement = statement.where(MessageDelivery.message_id.in_(subquery))
        return list((await self._session.execute(statement)).scalars())

    async def mark_read_receipts(
        self, recipient: UUID, conversation_id: UUID, up_to_seq: int
    ) -> list[UUID]:
        now = datetime.now(UTC)
        statement = (
            update(MessageDelivery)
            .where(
                MessageDelivery.recipient_user_id == recipient,
                MessageDelivery.channel == "chikka",
                MessageDelivery.status.in_(("sent", "delivered")),
                MessageDelivery.message_id.in_(
                    select(Message.id).where(
                        Message.conversation_id == conversation_id, Message.seq <= up_to_seq
                    )
                ),
            )
            .values(
                status="read",
                read_at=now,
                delivered_at=func.coalesce(MessageDelivery.delivered_at, now),
            )
            .returning(MessageDelivery.message_id)
        )
        return list((await self._session.execute(statement)).scalars())

    async def advance_read(self, conversation_id: UUID, user_id: UUID, up_to_seq: int) -> int:
        """Read position only moves forward and never past the last message."""
        result = await self._session.execute(
            text(
                """
                update public.conversation_members cm
                   set last_read_seq = greatest(cm.last_read_seq, least(:up_to, c.last_seq)),
                       last_read_at = now()
                  from public.conversations c
                 where c.id = cm.conversation_id
                   and cm.conversation_id = :conversation_id and cm.user_id = :user_id
                returning cm.last_read_seq
                """
            ),
            {"conversation_id": conversation_id, "user_id": user_id, "up_to": up_to_seq},
        )
        return int(result.scalar_one())

    async def last_read_seq(self, conversation_id: UUID, user_id: UUID) -> int:
        statement = select(ConversationMember.last_read_seq).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
        return int((await self._session.execute(statement)).scalar_one_or_none() or 0)

    async def messages_by_ids(self, message_ids: Sequence[UUID]) -> list[Message]:
        if not message_ids:
            return []
        statement = select(Message).where(Message.id.in_(set(message_ids)))
        return list((await self._session.execute(statement)).scalars())

    # -- attachments -----------------------------------------------------------------------

    async def add_attachment(self, attachment: MessageAttachment) -> MessageAttachment:
        self._session.add(attachment)
        await self._session.flush()
        await self._session.refresh(attachment)
        return attachment

    async def pending_attachments(
        self, uploader: UUID, conversation_id: UUID, ids: Sequence[UUID]
    ) -> list[MessageAttachment]:
        """The caller's own, unsent uploads for this conversation, locked for linking."""
        if not ids:
            return []
        statement = (
            select(MessageAttachment)
            .where(
                MessageAttachment.id.in_(set(ids)),
                MessageAttachment.uploader_id == uploader,
                MessageAttachment.conversation_id == conversation_id,
                MessageAttachment.message_id.is_(None),
            )
            .with_for_update()
        )
        return list((await self._session.execute(statement)).scalars())

    async def link_attachments(self, ids: Sequence[UUID], message_id: UUID) -> None:
        await self._session.execute(
            update(MessageAttachment)
            .where(MessageAttachment.id.in_(set(ids)))
            .values(message_id=message_id)
        )

    async def attachments_for(
        self, message_ids: Sequence[UUID]
    ) -> dict[UUID, list[MessageAttachment]]:
        if not message_ids:
            return {}
        statement = (
            select(MessageAttachment)
            .where(MessageAttachment.message_id.in_(set(message_ids)))
            .order_by(MessageAttachment.created_at, MessageAttachment.id)
        )
        grouped: dict[UUID, list[MessageAttachment]] = {}
        for row in (await self._session.execute(statement)).scalars():
            if row.message_id is not None:
                grouped.setdefault(row.message_id, []).append(row)
        return grouped

    # -- people ----------------------------------------------------------------------------

    async def profiles(self, user_ids: Sequence[UUID]) -> dict[UUID, Profile]:
        if not user_ids:
            return {}
        statement = select(Profile).where(Profile.id.in_(set(user_ids)))
        return {p.id: p for p in (await self._session.execute(statement)).scalars()}
