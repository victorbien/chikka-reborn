from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.profiles.models import Profile


class UsernameTakenError(Exception):
    pass


def _is_unique_violation(exc: IntegrityError) -> bool:
    original = exc.orig
    code = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    return code == "23505"


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> Profile | None:
        return await self._session.get(Profile, user_id)

    async def get_for_update(self, user_id: UUID) -> Profile | None:
        statement = select(Profile).where(Profile.id == user_id).with_for_update()
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def exists(self, user_id: UUID) -> bool:
        statement = select(func.count()).select_from(Profile).where(Profile.id == user_id)
        return bool((await self._session.execute(statement)).scalar_one())

    async def username_taken(self, username: str) -> bool:
        statement = (
            select(func.count())
            .select_from(Profile)
            .where(func.lower(Profile.username) == username.lower())
        )
        return bool((await self._session.execute(statement)).scalar_one())

    async def apply(self, profile: Profile, changes: dict[str, Any]) -> Profile:
        """Set attributes and flush. A username clash raises UsernameTakenError."""
        for field, value in changes.items():
            setattr(profile, field, value)
        try:
            async with self._session.begin_nested():
                await self._session.flush()
        except IntegrityError as exc:
            if _is_unique_violation(exc) and "username" in changes:
                raise UsernameTakenError from exc
            raise
        # updated_at is maintained by a trigger; reload server-side values.
        await self._session.refresh(profile)
        return profile

    async def activate_if_pending(self, user_id: UUID) -> bool:
        statement = (
            update(Profile)
            .where(Profile.id == user_id, Profile.status == "pending_verification")
            .values(status="active")
        )
        result = await self._session.execute(statement)
        return bool(getattr(result, "rowcount", 0))

    async def touch_last_seen(self, user_id: UUID, when: datetime) -> None:
        await self._session.execute(
            update(Profile).where(Profile.id == user_id).values(last_seen_at=when)
        )
