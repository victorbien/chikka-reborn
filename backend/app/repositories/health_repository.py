import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class HealthRepository:
    """Only layer that touches SQLAlchemy for health checks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(self) -> bool:
        try:
            await self._session.execute(text("select 1"))
        except (SQLAlchemyError, OSError) as exc:
            logger.warning("database ping failed", extra={"error_type": type(exc).__name__})
            return False
        return True
