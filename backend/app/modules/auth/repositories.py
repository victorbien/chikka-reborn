from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import PhoneNumber


class PhoneAlreadyVerifiedError(Exception):
    """Unique index: the number is verified on another account in this mode."""


class PhoneRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def verified_for_user(self, user_id: UUID, mode: str) -> PhoneNumber | None:
        statement = select(PhoneNumber).where(
            PhoneNumber.user_id == user_id,
            PhoneNumber.verification_mode == mode,
            PhoneNumber.status == "verified",
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def any_verified_for_user(self, user_id: UUID) -> PhoneNumber | None:
        statement = (
            select(PhoneNumber)
            .where(PhoneNumber.user_id == user_id, PhoneNumber.status == "verified")
            .order_by(PhoneNumber.verified_at.desc())
            .limit(1)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def verified_elsewhere(self, e164: str, mode: str, user_id: UUID) -> bool:
        statement = select(PhoneNumber.id).where(
            PhoneNumber.e164 == e164,
            PhoneNumber.verification_mode == mode,
            PhoneNumber.status == "verified",
            PhoneNumber.user_id != user_id,
        )
        return (await self._session.execute(statement)).first() is not None

    async def pending_for_update(self, user_id: UUID, e164: str, mode: str) -> PhoneNumber | None:
        statement = (
            select(PhoneNumber)
            .where(
                PhoneNumber.user_id == user_id,
                PhoneNumber.e164 == e164,
                PhoneNumber.verification_mode == mode,
                PhoneNumber.status == "pending",
            )
            .with_for_update()
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def create_pending(
        self, *, user_id: UUID, e164: str, country_code: str, mode: str
    ) -> PhoneNumber:
        row = PhoneNumber(
            user_id=user_id,
            e164=e164,
            country_code=country_code,
            verification_mode=mode,
            status="pending",
            otp_attempts=0,
            otp_sent_count=0,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def flush(self) -> None:
        await self._session.flush()

    async def mark_verified(self, row: PhoneNumber, when: datetime) -> None:
        row.status = "verified"
        row.verified_at = when
        row.otp_hash = None
        row.otp_expires_at = None
        try:
            async with self._session.begin_nested():
                await self._session.flush()
        except IntegrityError as exc:
            raise PhoneAlreadyVerifiedError from exc

    async def release_verified(self, user_id: UUID, when: datetime, mode: str | None = None) -> int:
        statement = update(PhoneNumber).where(
            PhoneNumber.user_id == user_id, PhoneNumber.status == "verified"
        )
        if mode is not None:
            statement = statement.where(PhoneNumber.verification_mode == mode)
        result = await self._session.execute(statement.values(status="released", released_at=when))
        return int(getattr(result, "rowcount", 0))

    async def release_all(self, user_id: UUID, when: datetime) -> None:
        """Account deletion: detach every number and drop pending codes."""
        await self._session.execute(
            update(PhoneNumber)
            .where(PhoneNumber.user_id == user_id, PhoneNumber.status != "released")
            .values(status="released", released_at=when, otp_hash=None, otp_expires_at=None)
        )


_INSERT_CONSENT = text(
    """
    insert into public.user_consents
        (user_id, consent_type, notice_version, decision, source, ip_prefix)
    values
        (:user_id, :consent_type, :notice_version, 'granted', :source, :ip_prefix)
    """
)


class ConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def grant(
        self,
        *,
        user_id: UUID,
        consent_type: str,
        notice_version: str,
        source: str,
        ip_prefix: str | None,
    ) -> None:
        await self._session.execute(
            _INSERT_CONSENT,
            {
                "user_id": user_id,
                "consent_type": consent_type,
                "notice_version": notice_version,
                "source": source,
                "ip_prefix": ip_prefix,
            },
        )


@dataclass(frozen=True)
class SessionRecord:
    id: UUID
    created_at: datetime
    last_active_at: datetime | None
    user_agent: str | None
    ip: str | None


class AuthSessionRepository:
    """Reads Supabase Auth's own auth.sessions table (the backend connects as a privileged role).

    Deleting a row revokes that session: its refresh tokens are removed by GoTrue's cascade and
    the access-token check below fails on the next request.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_active(self, session_id: UUID, user_id: UUID) -> bool:
        result = await self._session.execute(
            text(
                """
                select 1 from auth.sessions
                where id = :id and user_id = :user_id and (not_after is null or not_after > now())
                """
            ),
            {"id": session_id, "user_id": user_id},
        )
        return result.first() is not None

    async def list_for_user(self, user_id: UUID) -> list[SessionRecord]:
        result = await self._session.execute(
            text(
                """
                select id, created_at, coalesce(updated_at, created_at), user_agent, host(ip)
                from auth.sessions
                where user_id = :user_id and (not_after is null or not_after > now())
                order by coalesce(updated_at, created_at) desc
                limit 50
                """
            ),
            {"user_id": user_id},
        )
        return [
            SessionRecord(id=r[0], created_at=r[1], last_active_at=r[2], user_agent=r[3], ip=r[4])
            for r in result.all()
        ]

    async def delete(self, session_id: UUID, user_id: UUID) -> bool:
        result = await self._session.execute(
            text("delete from auth.sessions where id = :id and user_id = :user_id"),
            {"id": session_id, "user_id": user_id},
        )
        return bool(getattr(result, "rowcount", 0))

    async def delete_all_except(self, user_id: UUID, keep: UUID | None) -> int:
        result = await self._session.execute(
            text(
                """
                delete from auth.sessions
                where user_id = :user_id
                  and (cast(:keep as uuid) is null or id <> cast(:keep as uuid))
                """
            ),
            {"user_id": user_id, "keep": keep},
        )
        return int(getattr(result, "rowcount", 0))
