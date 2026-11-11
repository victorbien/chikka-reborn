from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Fixed window counter. The window restarts when it has passed. Values are bound parameters.
_HIT = text(
    """
    insert into public.rate_limit_counters as c (scope, subject_hash, window_start, attempts)
    values (:scope, :subject, now(), 1)
    on conflict (scope, subject_hash) do update set
        window_start = case
            when c.window_start <= now() - make_interval(secs => cast(:window as double precision))
            then now() else c.window_start end,
        attempts = case
            when c.window_start <= now() - make_interval(secs => cast(:window as double precision))
            then 1 else c.attempts + 1 end
    returning
        attempts,
        greatest(1, ceil(extract(epoch from (
            c.window_start
            + make_interval(secs => cast(:window as double precision))
            - now()
        ))))::int as retry_after
    """
)

_LOCK = text(
    """
    update public.rate_limit_counters
    set attempts = 0,
        window_start = now(),
        locked_until = now() + make_interval(secs => cast(:lock as double precision))
    where scope = :scope and subject_hash = :subject
    """
)

_LOCKED_FOR = text(
    """
    select ceil(extract(epoch from (locked_until - now())))::int
    from public.rate_limit_counters
    where scope = :scope and subject_hash = :subject and locked_until > now()
    """
)

_RESET = text(
    "delete from public.rate_limit_counters where scope = :scope and subject_hash = :subject"
)


@dataclass(frozen=True)
class HitResult:
    attempts: int
    retry_after: int


class RateLimitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def hit(self, scope: str, subject: str, window_seconds: int) -> HitResult:
        row = (
            await self._session.execute(
                _HIT, {"scope": scope, "subject": subject, "window": float(window_seconds)}
            )
        ).one()
        return HitResult(attempts=int(row[0]), retry_after=int(row[1]))

    async def lock(self, scope: str, subject: str, lock_seconds: int) -> None:
        await self._session.execute(
            _LOCK, {"scope": scope, "subject": subject, "lock": float(lock_seconds)}
        )

    async def locked_for(self, scope: str, subject: str) -> int | None:
        value = (
            await self._session.execute(_LOCKED_FOR, {"scope": scope, "subject": subject})
        ).scalar_one_or_none()
        return int(value) if value is not None else None

    async def reset(self, scope: str, subject: str) -> None:
        await self._session.execute(_RESET, {"scope": scope, "subject": subject})
