"""Public interface of the notifications module for other modules (Module G, in-app feed).

Creation is backend-only (see the notifications RLS policies). Callers pass their own session so
the notification commits with the change that caused it. Bodies are left empty unless the user
enabled previews; SMS content is never copied here.
"""

from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

NotificationType = Literal[
    "new_message",
    "sms_inbound",
    "sms_delivered",
    "sms_failed",
    "contact_request",
    "contact_accepted",
    "low_balance",
    "system",
]

_INSERT = text(
    """
    insert into public.notifications
        (user_id, notification_type, title, body, reference_type, reference_id, group_key)
    values
        (:user_id, :notification_type, :title, :body, :reference_type, :reference_id, :group_key)
    """
)


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
) -> None:
    await session.execute(
        _INSERT,
        {
            "user_id": user_id,
            "notification_type": notification_type,
            "title": title[:200],
            "body": body[:500] if body else None,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "group_key": group_key,
        },
    )
