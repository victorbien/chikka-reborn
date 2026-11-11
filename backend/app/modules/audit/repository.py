import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INSERT = text(
    """
    insert into public.audit_logs
        (category, action, outcome, actor_id, actor_role, target_type, target_id,
         request_id, ip_prefix, metadata)
    values
        (:category, :action, :outcome, :actor_id, :actor_role, :target_type, :target_id,
         :request_id, :ip_prefix, cast(:metadata as jsonb))
    """
)


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        category: str,
        action: str,
        outcome: str,
        actor_id: UUID | None,
        actor_role: str | None,
        target_type: str | None,
        target_id: str | None,
        request_id: str | None,
        ip_prefix: str | None,
        metadata: dict[str, Any],
    ) -> None:
        await self._session.execute(
            _INSERT,
            {
                "category": category,
                "action": action,
                "outcome": outcome,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "target_type": target_type,
                "target_id": target_id,
                "request_id": request_id,
                "ip_prefix": ip_prefix,
                "metadata": json.dumps(metadata),
            },
        )
