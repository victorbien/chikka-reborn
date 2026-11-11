from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import AuthenticatedUser, decode_access_token
from app.database.session import Database, session_scope

SettingsDep = Annotated[Settings, Depends(get_settings)]

# auto_error=False so a missing header goes through our error envelope, not FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False, description="Supabase access token")


def get_database(request: Request) -> Database | None:
    database: Database | None = request.app.state.database
    return database


DatabaseDep = Annotated[Database | None, Depends(get_database)]


async def get_db_session(database: DatabaseDep) -> AsyncIterator[AsyncSession]:
    async for session in session_scope(database):
        yield session


async def get_optional_db_session(database: DatabaseDep) -> AsyncIterator[AsyncSession | None]:
    """Like get_db_session, but yields None when no database is configured."""
    if database is None:
        yield None
        return
    async for session in session_scope(database):
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AuthenticatedUser:
    """Require a valid Supabase access token. Every protected route depends on this."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication is required.")
    return decode_access_token(credentials.credentials, settings)


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]


async def require_admin(user: CurrentUserDep) -> AuthenticatedUser:
    if user.role != "admin":
        raise PermissionDeniedError("You do not have permission to do this.")
    return user


AdminUserDep = Annotated[AuthenticatedUser, Depends(require_admin)]
