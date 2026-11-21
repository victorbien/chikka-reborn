"""Database access for notifications. The service owns the transaction.

Raw SQL with bound parameters only. The recipient's time zone is a narrow read of
`profiles.time_zone`, kept here until the profiles module exposes it.
"""

import json
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.preferences import Preferences

_COLUMNS = """
    n.id, n.user_id, n.notification_type, n.title, n.body, n.reference_type, n.reference_id,
    n.occurrence_count, n.read_at, n.created_at
"""
_LIVE = "n.dismissed_at is null and n.expires_at > now()"


@dataclass(frozen=True)
class Recipient:
    preferences: Preferences


def _preferences(row: Any) -> Preferences:
    return Preferences(
        overrides={k: bool(v) for k, v in (row["overrides"] or {}).items()},
        quiet_hours_start=row["quiet_hours_start"],
        quiet_hours_end=row["quiet_hours_end"],
        show_previews=bool(row["show_previews"]),
        low_balance_threshold_units=int(row["low_balance_threshold_units"]),
        time_zone=row["time_zone"] or "UTC",
        email_disabled=row["email_disabled_at"] is not None,
    )


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- preferences -----------------------------------------------------------------------

    async def preferences(self, user_id: UUID) -> Preferences | None:
        """None when the user does not exist. A user with no row gets the defaults."""
        row = (
            (
                await self._session.execute(
                    text(
                        """
                        select p.time_zone, np.overrides, np.quiet_hours_start,
                               np.quiet_hours_end,
                               coalesce(np.show_previews, false) as show_previews,
                               coalesce(np.low_balance_threshold_units, 500)
                                   as low_balance_threshold_units,
                               np.email_disabled_at
                        from public.profiles p
                        left join public.notification_preferences np on np.user_id = p.id
                        where p.id = :user_id
                        """
                    ),
                    {"user_id": user_id},
                )
            )
            .mappings()
            .first()
        )
        return _preferences(row) if row else None

    async def save_preferences(
        self,
        user_id: UUID,
        *,
        overrides: dict[str, bool],
        quiet_start: time | None,
        quiet_end: time | None,
        show_previews: bool,
        threshold_units: int,
    ) -> None:
        await self._session.execute(
            text(
                """
                insert into public.notification_preferences
                    (user_id, overrides, quiet_hours_start, quiet_hours_end, show_previews,
                     low_balance_threshold_units)
                values (:user_id, cast(:overrides as jsonb), :start, :end, :previews, :threshold)
                on conflict (user_id) do update set
                    overrides = excluded.overrides,
                    quiet_hours_start = excluded.quiet_hours_start,
                    quiet_hours_end = excluded.quiet_hours_end,
                    show_previews = excluded.show_previews,
                    low_balance_threshold_units = excluded.low_balance_threshold_units
                """
            ),
            {
                "user_id": user_id,
                "overrides": json.dumps(overrides),
                "start": quiet_start,
                "end": quiet_end,
                "previews": show_previews,
                "threshold": threshold_units,
            },
        )

    # -- creating --------------------------------------------------------------------------

    async def dedupe_exists(self, user_id: UUID, dedupe_key: str) -> bool:
        result = await self._session.execute(
            text(
                "select 1 from public.notifications where user_id = :u and dedupe_key = :k limit 1"
            ),
            {"u": user_id, "k": dedupe_key},
        )
        return result.first() is not None

    async def bump_group(
        self,
        *,
        user_id: UUID,
        group_key: str,
        title: str,
        body: str | None,
        reference_type: str | None,
        reference_id: UUID | None,
        browser_push: bool,
    ) -> UUID | None:
        """Fold a new event into the open (unread) notification of the same group."""
        result = await self._session.execute(
            text(
                """
                update public.notifications
                   set occurrence_count = occurrence_count + 1,
                       created_at = now(),
                       announced_at = null,
                       title = :title, body = :body,
                       reference_type = :reference_type, reference_id = :reference_id,
                       browser_push = :browser_push
                 where user_id = :user_id and group_key = :group_key
                   and read_at is null and dismissed_at is null
                returning id
                """
            ),
            {
                "user_id": user_id,
                "group_key": group_key,
                "title": title,
                "body": body,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "browser_push": browser_push,
            },
        )
        found = result.scalar_one_or_none()
        return UUID(str(found)) if found else None

    async def insert(
        self,
        *,
        user_id: UUID,
        notification_type: str,
        title: str,
        body: str | None,
        reference_type: str | None,
        reference_id: UUID | None,
        group_key: str | None,
        dedupe_key: str | None,
        browser_push: bool,
        email_requested: bool,
        hidden: bool,
        now: datetime,
    ) -> UUID | None:
        """Insert one row. Returns None when the dedupe key already exists."""
        result = await self._session.execute(
            text(
                """
                insert into public.notifications
                    (user_id, notification_type, title, body, reference_type, reference_id,
                     group_key, dedupe_key, browser_push, email_requested_at, read_at, dismissed_at)
                values
                    (:user_id, :notification_type, :title, :body, :reference_type, :reference_id,
                     :group_key, :dedupe_key, :browser_push,
                     case when :email_requested then cast(:now as timestamptz) end,
                     case when :hidden then cast(:now as timestamptz) end,
                     case when :hidden then cast(:now as timestamptz) end)
                on conflict (user_id, dedupe_key) where dedupe_key is not null do nothing
                returning id
                """
            ),
            {
                "user_id": user_id,
                "notification_type": notification_type,
                "title": title,
                "body": body,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "group_key": group_key,
                "dedupe_key": dedupe_key,
                "browser_push": browser_push,
                "email_requested": email_requested,
                "hidden": hidden,
                "now": now,
            },
        )
        found = result.scalar_one_or_none()
        return UUID(str(found)) if found else None

    # -- reading ---------------------------------------------------------------------------

    async def feed(
        self,
        user_id: UUID,
        *,
        unread_only: bool,
        kind: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = f"n.user_id = :user_id and {_LIVE}"
        if unread_only:
            filters += " and n.read_at is null"
        if kind:
            filters += " and n.notification_type = :kind"
        params: dict[str, Any] = {"user_id": user_id, "kind": kind}
        total = (
            await self._session.execute(
                text(f"select count(*) from public.notifications n where {filters}"),  # noqa: S608
                params,
            )
        ).scalar_one()
        rows = (
            (
                await self._session.execute(
                    text(
                        f"select {_COLUMNS} from public.notifications n where {filters} "  # noqa: S608
                        "order by n.created_at desc, n.id limit :limit offset :offset"
                    ),
                    {**params, "limit": limit, "offset": offset},
                )
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows], int(total)

    async def unread_count(self, user_id: UUID) -> int:
        result = await self._session.execute(
            text(
                "select count(*) from public.notifications n "  # noqa: S608
                f"where n.user_id = :user_id and n.read_at is null and {_LIVE}"
            ),
            {"user_id": user_id},
        )
        return int(result.scalar_one())

    async def get(self, user_id: UUID, notification_id: UUID) -> dict[str, Any] | None:
        row = (
            (
                await self._session.execute(
                    text(
                        f"select {_COLUMNS} from public.notifications n "  # noqa: S608
                        "where n.id = :id and n.user_id = :user_id"
                    ),
                    {"id": notification_id, "user_id": user_id},
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    async def mark_read(self, user_id: UUID, notification_id: UUID) -> bool:
        """True when the notification exists (read now or already read)."""
        result = await self._session.execute(
            text(
                """
                update public.notifications
                   set read_at = coalesce(read_at, now())
                 where id = :id and user_id = :user_id and dismissed_at is null
                returning id
                """
            ),
            {"id": notification_id, "user_id": user_id},
        )
        return result.first() is not None

    async def mark_all_read(self, user_id: UUID, kind: str | None) -> int:
        result = await self._session.execute(
            text(
                """
                update public.notifications
                   set read_at = now()
                 where user_id = :user_id and read_at is null and dismissed_at is null
                   and (cast(:kind as text) is null or notification_type = :kind)
                returning id
                """
            ),
            {"user_id": user_id, "kind": kind},
        )
        return len(result.all())

    async def dismiss(self, user_id: UUID, notification_id: UUID) -> bool:
        result = await self._session.execute(
            text(
                """
                update public.notifications
                   set dismissed_at = coalesce(dismissed_at, now()),
                       read_at = coalesce(read_at, now())
                 where id = :id and user_id = :user_id
                returning id
                """
            ),
            {"id": notification_id, "user_id": user_id},
        )
        return result.first() is not None

    # -- outbox (worker) -------------------------------------------------------------------

    async def claim_unannounced(self, limit: int) -> list[dict[str, Any]]:
        rows = (
            (
                await self._session.execute(
                    text(
                        f"""
                        with due as (
                            select id from public.notifications
                            where announced_at is null
                            order by created_at limit :limit
                            for update skip locked
                        )
                        update public.notifications n set announced_at = now()
                          from due where n.id = due.id
                        returning {_COLUMNS}, n.browser_push
                        """  # noqa: S608
                    ),
                    {"limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    async def claim_for_email(
        self, *, now: datetime, retry_after_seconds: int, max_attempts: int, limit: int
    ) -> list[dict[str, Any]]:
        rows = (
            (
                await self._session.execute(
                    text(
                        """
                        with due as (
                            select id from public.notifications
                            where email_requested_at is not null and email_sent_at is null
                              and email_attempts < :max_attempts
                              and (email_attempted_at is null or email_attempted_at
                                   <= cast(:now as timestamptz)
                                      - make_interval(
                                          secs => cast(:retry as integer) * email_attempts))
                            order by created_at limit :limit
                            for update skip locked
                        )
                        update public.notifications n
                           set email_attempts = n.email_attempts + 1,
                               email_attempted_at = cast(:now as timestamptz)
                          from due where n.id = due.id
                        returning n.id, n.user_id, n.title, n.body, n.notification_type
                        """
                    ),
                    {
                        "now": now,
                        "retry": retry_after_seconds,
                        "max_attempts": max_attempts,
                        "limit": limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    async def email_address(self, user_id: UUID) -> str | None:
        """The sign-in address. auth.users is readable by the backend's database role only."""
        result = await self._session.execute(
            text("select email from auth.users where id = :user_id"), {"user_id": user_id}
        )
        value = result.scalar_one_or_none()
        return str(value) if value else None

    async def email_enabled(self, user_id: UUID) -> bool:
        result = await self._session.execute(
            text(
                "select email_disabled_at is null from public.notification_preferences "
                "where user_id = :user_id"
            ),
            {"user_id": user_id},
        )
        value = result.scalar_one_or_none()
        return True if value is None else bool(value)

    async def mark_email_sent(self, notification_id: UUID, now: datetime) -> None:
        await self._session.execute(
            text("update public.notifications set email_sent_at = :now where id = :id"),
            {"id": notification_id, "now": now},
        )

    async def give_up_on_email(self, notification_id: UUID, max_attempts: int) -> None:
        await self._session.execute(
            text("update public.notifications set email_attempts = :max where id = :id"),
            {"id": notification_id, "max": max_attempts},
        )

    async def record_hard_bounce(self, user_id: UUID, disable_after: int) -> None:
        await self._session.execute(
            text(
                """
                update public.notification_preferences
                   set email_hard_bounce_count = email_hard_bounce_count + 1,
                       email_disabled_at = case
                           when email_hard_bounce_count + 1 >= :limit
                           then coalesce(email_disabled_at, now()) else email_disabled_at end
                 where user_id = :user_id
                """
            ),
            {"user_id": user_id, "limit": disable_after},
        )

    # -- administration --------------------------------------------------------------------

    async def active_user_ids(self) -> list[UUID]:
        result = await self._session.execute(
            text("select id from public.profiles where status = 'active' order by id")
        )
        return [UUID(str(row[0])) for row in result]

    async def user_exists(self, user_id: UUID) -> bool:
        result = await self._session.execute(
            text("select 1 from public.profiles where id = :id and status = 'active'"),
            {"id": user_id},
        )
        return result.first() is not None
