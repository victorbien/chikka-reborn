"""Notifications (Module G): the public interface for other modules, and the user-facing service.

`create_notification` is how other modules raise a notification. They pass their own session so
the notification commits with the change that caused it, and a `dedupe_key` naming the event so
the same event can never notify twice. It honours the recipient's preferences:

* a type switched off on every channel creates nothing;
* in-app off (never allowed for failed SMS, system and security notices) hides the row but keeps
  push or email delivery;
* quiet hours suppress browser notifications and email, not the feed;
* the body is dropped for message notifications unless the user enabled previews.

Rows are announced to open sessions and emailed by the dispatcher after the transaction commits
(modules/notifications/dispatcher.py). SMS content is never copied here.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, UnprocessableError
from app.core.security import AuthenticatedUser
from app.database.session import Database
from app.modules.audit.service import AuditLogger
from app.modules.notifications.preferences import (
    CHANNELS,
    MANDATORY_IN_APP,
    TYPES,
    NotificationType,
    Preferences,
    overrides_for,
)
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import (
    AnnouncementOut,
    AnnouncementRequest,
    MarkAllReadOut,
    NotificationOut,
    PreferencesOut,
    PreferencesUpdate,
    PreferenceTypeOut,
    UnreadCountOut,
)

logger = logging.getLogger(__name__)

__all__ = ["NotificationService", "NotificationType", "create_notification"]

MAX_ANNOUNCEMENT_RECIPIENTS = 10_000


async def create_notification(
    session: AsyncSession,
    *,
    user_id: UUID,
    notification_type: NotificationType,
    title: str,
    body: str | None = None,
    reference_type: str | None = None,
    reference_id: UUID | None = None,
    group_key: str | None = None,
    dedupe_key: str | None = None,
    now: datetime | None = None,
) -> UUID | None:
    """Raise one notification. Returns its id, or None when nothing was created (the event was
    already notified, or the user turned this type off everywhere)."""
    repository = NotificationRepository(session)
    prefs = await repository.preferences(user_id)
    if prefs is None:
        return None
    moment = now or datetime.now(UTC)

    in_app = prefs.wants(notification_type, "in_app")
    quiet = prefs.is_quiet(moment)
    browser = prefs.wants(notification_type, "push") and not quiet
    email = prefs.wants(notification_type, "email") and not quiet and not prefs.email_disabled
    if not (in_app or browser or email):
        return None

    title = title[:200]
    body = body[:500] if body and prefs.keeps_body(notification_type) else None

    if dedupe_key is not None and await repository.dedupe_exists(user_id, dedupe_key):
        return None
    if group_key is not None and in_app:
        grouped = await repository.bump_group(
            user_id=user_id,
            group_key=group_key,
            title=title,
            body=body,
            reference_type=reference_type,
            reference_id=reference_id,
            browser_push=browser,
        )
        if grouped is not None:
            return grouped
    return await repository.insert(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        reference_type=reference_type,
        reference_id=reference_id,
        # A grouped key only applies to rows that stay visible in the feed.
        group_key=group_key if in_app else None,
        dedupe_key=dedupe_key,
        browser_push=browser,
        email_requested=email,
        hidden=not in_app,
        now=moment,
    )


def _to_out(row: dict[str, Any]) -> NotificationOut:
    return NotificationOut(
        id=row["id"],
        type=row["notification_type"],
        title=str(row["title"]),
        body=row["body"],
        reference_type=row["reference_type"],
        reference_id=row["reference_id"],
        occurrence_count=int(row["occurrence_count"]),
        is_read=row["read_at"] is not None,
        created_at=row["created_at"],
    )


def notification_payload(row: dict[str, Any]) -> dict[str, Any]:
    """JSON form of a notification row, for realtime events."""
    return _to_out(row).model_dump(mode="json")


def _clock_string(value: object) -> str | None:
    return None if value is None else str(value)[:5]


class NotificationService:
    def __init__(
        self,
        *,
        database: Database,
        audit: AuditLogger,
        email_simulated: bool,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._db = database
        self._audit = audit
        self._email_simulated = email_simulated
        self._clock = clock

    # -- feed ------------------------------------------------------------------------------

    async def feed(
        self,
        user: AuthenticatedUser,
        *,
        unread_only: bool,
        kind: NotificationType | None,
        page: int,
        page_size: int,
    ) -> tuple[list[NotificationOut], int]:
        async with self._db.transaction() as session:
            rows, total = await NotificationRepository(session).feed(
                user.id,
                unread_only=unread_only,
                kind=kind,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
        return [_to_out(row) for row in rows], total

    async def unread_count(self, user: AuthenticatedUser) -> UnreadCountOut:
        async with self._db.transaction() as session:
            return UnreadCountOut(
                unread_count=await NotificationRepository(session).unread_count(user.id)
            )

    async def mark_read(self, user: AuthenticatedUser, notification_id: UUID) -> NotificationOut:
        async with self._db.transaction() as session:
            repository = NotificationRepository(session)
            if not await repository.mark_read(user.id, notification_id):
                raise NotFoundError("Notification not found.")
            row = await repository.get(user.id, notification_id)
        if row is None:  # pragma: no cover - read in the same transaction
            raise NotFoundError("Notification not found.")
        return _to_out(row)

    async def mark_all_read(
        self, user: AuthenticatedUser, kind: NotificationType | None
    ) -> MarkAllReadOut:
        async with self._db.transaction() as session:
            repository = NotificationRepository(session)
            updated = await repository.mark_all_read(user.id, kind)
            remaining = await repository.unread_count(user.id)
        return MarkAllReadOut(updated=updated, unread_count=remaining)

    async def dismiss(self, user: AuthenticatedUser, notification_id: UUID) -> UnreadCountOut:
        async with self._db.transaction() as session:
            repository = NotificationRepository(session)
            if not await repository.dismiss(user.id, notification_id):
                raise NotFoundError("Notification not found.")
            return UnreadCountOut(unread_count=await repository.unread_count(user.id))

    # -- preferences -----------------------------------------------------------------------

    def _preferences_out(self, prefs: Preferences) -> PreferencesOut:
        return PreferencesOut(
            types=[
                PreferenceTypeOut(
                    type=kind,
                    in_app=prefs.wants(kind, "in_app"),
                    push=prefs.wants(kind, "push"),
                    email=prefs.wants(kind, "email"),
                    in_app_locked=kind in MANDATORY_IN_APP,
                )
                for kind in TYPES
            ],
            quiet_hours_start=_clock_string(prefs.quiet_hours_start),
            quiet_hours_end=_clock_string(prefs.quiet_hours_end),
            show_previews=prefs.show_previews,
            low_balance_threshold_units=prefs.low_balance_threshold_units,
            low_balance_threshold_credits=prefs.low_balance_threshold_units / 100,
            email_disabled=prefs.email_disabled,
            email_simulated=self._email_simulated,
        )

    async def preferences(self, user: AuthenticatedUser) -> PreferencesOut:
        async with self._db.transaction() as session:
            prefs = await NotificationRepository(session).preferences(user.id)
        if prefs is None:
            raise NotFoundError("Account not found.")
        return self._preferences_out(prefs)

    async def update_preferences(
        self, user: AuthenticatedUser, update: PreferencesUpdate
    ) -> PreferencesOut:
        async with self._db.transaction() as session:
            repository = NotificationRepository(session)
            current = await repository.preferences(user.id)
            if current is None:
                raise NotFoundError("Account not found.")

            matrix: dict[str, dict[str, bool]] = {
                kind: {channel: current.wants(kind, channel) for channel in CHANNELS}
                for kind in TYPES
            }
            for kind, patch in (update.types or {}).items():
                for channel, value in patch.model_dump(exclude_none=True).items():
                    if channel == "in_app" and value is False and kind in MANDATORY_IN_APP:
                        raise UnprocessableError(
                            "This notice always appears in the app and cannot be switched off.",
                            code="notification_mandatory",
                            details={"type": kind},
                        )
                    matrix[kind][channel] = value

            start, end = current.quiet_hours_start, current.quiet_hours_end
            if "quiet_hours_start" in update.model_fields_set:
                start, end = update.quiet_hours_start, update.quiet_hours_end
            previews = (
                current.show_previews if update.show_previews is None else update.show_previews
            )
            threshold = (
                current.low_balance_threshold_units
                if update.low_balance_threshold_units is None
                else update.low_balance_threshold_units
            )
            await repository.save_preferences(
                user.id,
                overrides=overrides_for(matrix),
                quiet_start=start,
                quiet_end=end,
                show_previews=previews,
                threshold_units=threshold,
            )
            saved = await repository.preferences(user.id)
        if saved is None:  # pragma: no cover
            raise NotFoundError("Account not found.")
        return self._preferences_out(saved)

    # -- administration --------------------------------------------------------------------

    async def announce(
        self, admin: AuthenticatedUser, request: AnnouncementRequest, key: UUID, ip: str | None
    ) -> AnnouncementOut:
        """A system notice from an administrator. Repeating the same key creates nothing new."""
        async with self._db.transaction() as session:
            repository = NotificationRepository(session)
            if request.user_id is not None:
                if not await repository.user_exists(request.user_id):
                    raise NotFoundError("User not found.")
                recipients = [request.user_id]
            else:
                recipients = await repository.active_user_ids()
            if len(recipients) > MAX_ANNOUNCEMENT_RECIPIENTS:
                raise UnprocessableError("Too many recipients.", code="too_many_recipients")
            created = 0
            for recipient in recipients:
                made = await create_notification(
                    session,
                    user_id=recipient,
                    notification_type="system",
                    title=request.title,
                    body=request.body,
                    dedupe_key=f"admin_notice:{key}",
                    now=self._clock(),
                )
                created += 1 if made is not None else 0
            await self._audit.record(
                session,
                category="admin",
                action="notification.announced",
                actor_id=admin.id,
                actor_role=admin.role,
                target_type="user" if request.user_id else "all_users",
                target_id=str(request.user_id) if request.user_id else None,
                ip=ip,
                metadata={"recipients": len(recipients), "created": created, "key": str(key)},
            )
        return AnnouncementOut(recipients=len(recipients), created=created)
