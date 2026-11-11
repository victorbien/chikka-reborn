from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.exceptions import ServiceUnavailableError


class Database:
    """Owns the async engine and session factory for the Supabase PostgreSQL connection."""

    def __init__(self, url: str, *, pool_size: int = 10, max_overflow: int = 20) -> None:
        self._engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            # Supabase's pooler (transaction mode) does not support prepared statements.
            connect_args={"statement_cache_size": 0, "timeout": 5},
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    def session(self) -> AsyncSession:
        return self._session_factory()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """One unit of work: commits on success, rolls back on any exception."""
        async with self._session_factory() as session, session.begin():
            yield session

    async def dispose(self) -> None:
        await self._engine.dispose()


def build_database(
    url: str | None, *, pool_size: int = 10, max_overflow: int = 20
) -> Database | None:
    """Return None when no DATABASE_URL is configured (the app still starts)."""
    if not url:
        return None
    return Database(url, pool_size=pool_size, max_overflow=max_overflow)


def require_database(database: Database | None) -> Database:
    """Auth and profile operations fail closed without a database (FR-AUTH-006)."""
    if database is None:
        raise ServiceUnavailableError(
            "The service is temporarily unavailable.",
            details={"reason": "database_not_configured"},
        )
    return database


async def session_scope(database: Database | None) -> AsyncIterator[AsyncSession]:
    """Yield one session per request. Services own commits; errors roll back."""
    if database is None:
        raise ServiceUnavailableError(
            "The database is not configured.", details={"reason": "database_not_configured"}
        )
    async with database.session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
