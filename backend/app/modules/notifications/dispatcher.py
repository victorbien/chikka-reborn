"""Delivers notifications after the transaction that created them has committed.

* Announce: new rows are pushed to the user's open sessions as `notification.created`
  (the browser decides whether to show a system notification from `browser_push`).
* Email: rows that asked for email are sent through the configured EmailProvider with retries.
  Attempts are counted before sending, so a crash never loops on one row.

Both are driven by the database, not by memory, so they survive restarts. The loop runs
in-process (single instance, like the SMS worker); tests call `run_once`.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.database.session import Database
from app.integrations.email.base import EmailError, EmailMessage, EmailProvider
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import notification_payload
from app.realtime.hub import RealtimeHub, event

logger = logging.getLogger(__name__)

MAX_EMAIL_ATTEMPTS = 3
EMAIL_RETRY_SECONDS = 60
BOUNCES_BEFORE_DISABLING = 3
BATCH = 50
# Upper bound per pass so one huge backlog cannot starve email sending.
MAX_ANNOUNCE_BATCHES = 40


class NotificationDispatcher:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        hub: RealtimeHub,
        email: EmailProvider,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._db = database
        self._hub = hub
        self._email = email
        self._clock = clock
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    # -- lifecycle -------------------------------------------------------------------------

    def start(self) -> None:
        if self._task is None:
            self._stopping.clear()
            self._task = asyncio.create_task(self._loop(), name="notification-dispatcher")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        interval = self._settings.notifications_worker_poll_seconds
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except Exception as exc:
                logger.error(
                    "notification dispatch failed", extra={"error_type": type(exc).__name__}
                )
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=interval)

    async def run_once(self) -> tuple[int, int]:
        """Returns (announced, emails sent)."""
        return await self.announce(), await self.send_emails()

    # -- announce --------------------------------------------------------------------------

    async def announce(self) -> int:
        """Announce everything pending, in batches, so a backlog never delays new rows."""
        total = 0
        for _ in range(MAX_ANNOUNCE_BATCHES):
            count = await self._announce_batch()
            total += count
            if count < BATCH:
                break
        return total

    async def _announce_batch(self) -> int:
        async with self._db.transaction() as session:
            repository = NotificationRepository(session)
            rows = await repository.claim_unannounced(BATCH)
            counts = {
                user_id: await repository.unread_count(user_id)
                for user_id in {row["user_id"] for row in rows}
            }
        for row in rows:
            payload: dict[str, Any] = {
                "notification": notification_payload(row),
                "browser": bool(row["browser_push"]),
                "unread_count": counts[row["user_id"]],
            }
            self._hub.publish([row["user_id"]], event("notification.created", payload))
        return len(rows)

    # -- email -----------------------------------------------------------------------------

    async def send_emails(self) -> int:
        now = self._clock()
        async with self._db.transaction() as session:
            claimed = await NotificationRepository(session).claim_for_email(
                now=now,
                retry_after_seconds=EMAIL_RETRY_SECONDS,
                max_attempts=MAX_EMAIL_ATTEMPTS,
                limit=BATCH,
            )
        sent = 0
        for row in claimed:
            sent += 1 if await self._send_one(row, now) else 0
        return sent

    async def _send_one(self, row: dict[str, Any], now: datetime) -> bool:
        notification_id: UUID = row["id"]
        user_id: UUID = row["user_id"]
        async with self._db.transaction() as session:
            repository = NotificationRepository(session)
            address = await repository.email_address(user_id)
            enabled = await repository.email_enabled(user_id)
            if address is None or not enabled:
                await repository.give_up_on_email(notification_id, MAX_EMAIL_ATTEMPTS)
                return False

        try:
            await self._email.send(
                EmailMessage(
                    to=address, subject=f"Chikka Reborn: {row['title']}", text=self._text(row)
                )
            )
        except EmailError as exc:
            logger.warning(
                "notification email failed",
                extra={"permanent": exc.permanent, "notification_type": row["notification_type"]},
            )
            if exc.permanent:
                async with self._db.transaction() as session:
                    repository = NotificationRepository(session)
                    await repository.give_up_on_email(notification_id, MAX_EMAIL_ATTEMPTS)
                    await repository.record_hard_bounce(user_id, BOUNCES_BEFORE_DISABLING)
            return False

        async with self._db.transaction() as session:
            await NotificationRepository(session).mark_email_sent(notification_id, now)
        return True

    def _text(self, row: dict[str, Any]) -> str:
        link = f"{self._settings.frontend_base_url.rstrip('/')}/notifications"
        lines = [str(row["title"])]
        if row["body"]:
            lines.append(str(row["body"]))
        lines += [
            "",
            f"Open Chikka Reborn: {link}",
            "",
            "You can choose which emails you get in Settings > Notifications.",
        ]
        if self._email.is_simulated:
            lines.append("(Simulated email: not sent to a real mailbox.)")
        return "\n".join(lines)
