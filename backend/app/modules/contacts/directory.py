"""Public interface of the contacts module for other modules (messaging).

Other modules ask "may these two people talk?" here instead of reading contact or block
tables themselves. Runs inside the caller's transaction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.repository import ContactRepository


@dataclass(frozen=True)
class Relationship:
    is_contact: bool
    # The viewer blocked the other person. Visible to the viewer.
    i_blocked: bool
    # The other person blocked the viewer. Never revealed to the viewer.
    they_blocked: bool

    @property
    def blocked_either_way(self) -> bool:
        return self.i_blocked or self.they_blocked


class ContactDirectory:
    def __init__(self, session: AsyncSession) -> None:
        self._repository = ContactRepository(session)

    async def relationships(
        self, viewer_id: UUID, others: Sequence[UUID]
    ) -> dict[UUID, Relationship]:
        contacts = await self._repository.contact_user_ids(viewer_id, others)
        blocked = await self._repository.blocked_by(viewer_id, others)
        blockers = await self._repository.blockers_of(viewer_id, others)
        return {
            other: Relationship(
                is_contact=other in contacts,
                i_blocked=other in blocked,
                they_blocked=other in blockers,
            )
            for other in others
        }

    async def blocked_by_me(self, viewer_id: UUID) -> set[UUID]:
        """Everyone the viewer blocked (their conversations leave the viewer's lists)."""
        return await self._repository.all_blocked_ids(viewer_id)

    async def relationship(self, viewer_id: UUID, other_id: UUID) -> Relationship:
        return (await self.relationships(viewer_id, [other_id]))[other_id]
