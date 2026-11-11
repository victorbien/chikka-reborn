"""Audit trail for auth, account and consent events (CC-03).

Never pass passwords, tokens, OTPs, message text or unmasked phone numbers in metadata. The
database rejects the obvious keys and unmasked numbers as a second guard.
"""

import logging
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import ip_prefix
from app.core.request_context import get_request_id
from app.database.session import Database
from app.modules.audit.repository import AuditRepository

logger = logging.getLogger(__name__)

AuditCategory = Literal["auth", "consent", "privacy", "security"]
AuditOutcome = Literal["success", "denied", "failure"]


class AuditLogger:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def record(
        self,
        session: AsyncSession,
        *,
        category: AuditCategory,
        action: str,
        outcome: AuditOutcome = "success",
        actor_id: UUID | None = None,
        actor_role: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        ip: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write inside the caller's transaction, so the event commits with the change."""
        await AuditRepository(session).insert(
            category=category,
            action=action,
            outcome=outcome,
            actor_id=actor_id,
            actor_role=actor_role,
            target_type=target_type,
            target_id=target_id,
            request_id=get_request_id(),
            ip_prefix=ip_prefix(ip),
            metadata=metadata or {},
        )

    async def record_standalone(self, **kwargs: Any) -> None:
        """Write in its own transaction. Used for denials, where the request rolls back."""
        try:
            async with self._database.transaction() as session:
                await self.record(session, **kwargs)
        except Exception as exc:
            # Losing an audit row must be visible, but must not change the user's outcome.
            logger.error(
                "audit write failed",
                extra={"error_type": type(exc).__name__, "audit_action": kwargs.get("action")},
            )
