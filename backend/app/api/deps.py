from collections.abc import AsyncIterator
from typing import Annotated, Protocol

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.container import Providers
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import AuthenticatedUser, TokenClaims, decode_access_token
from app.database.session import Database, require_database, session_scope
from app.modules.audit.service import AuditLogger
from app.modules.auth.account_service import AccountResolver, AccountService
from app.modules.auth.phone_service import PhoneVerificationService
from app.modules.auth.service import AuthService, RequestMeta
from app.modules.chat.service import ChatService
from app.modules.contacts.service import ContactService
from app.modules.profiles.service import ProfileService
from app.modules.rate_limits.service import RateLimiter

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


def get_required_database(database: DatabaseDep) -> Database:
    return require_database(database)


RequiredDatabaseDep = Annotated[Database, Depends(get_required_database)]


def get_providers(request: Request) -> Providers:
    providers: Providers = request.app.state.providers
    return providers


ProvidersDep = Annotated[Providers, Depends(get_providers)]


def get_request_meta(request: Request) -> RequestMeta:
    # request.client reflects X-Forwarded-For only when uvicorn runs with --proxy-headers and
    # a trusted --forwarded-allow-ips, so a client cannot spoof its address here.
    return RequestMeta(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


RequestMetaDep = Annotated[RequestMeta, Depends(get_request_meta)]


# -- services ----------------------------------------------------------------------------


def get_rate_limiter(database: RequiredDatabaseDep, settings: SettingsDep) -> RateLimiter:
    return RateLimiter(database, settings)


def get_audit_logger(database: RequiredDatabaseDep) -> AuditLogger:
    return AuditLogger(database)


RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
AuditLoggerDep = Annotated[AuditLogger, Depends(get_audit_logger)]


def get_auth_service(
    settings: SettingsDep,
    database: RequiredDatabaseDep,
    providers: ProvidersDep,
    limiter: RateLimiterDep,
    audit: AuditLoggerDep,
) -> AuthService:
    return AuthService(
        settings=settings,
        database=database,
        provider=providers.auth,
        limiter=limiter,
        audit=audit,
        presence=providers.presence,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_account_service(
    database: RequiredDatabaseDep,
    providers: ProvidersDep,
    auth_service: AuthServiceDep,
    audit: AuditLoggerDep,
) -> AccountService:
    return AccountService(
        database=database,
        provider=providers.auth,
        storage=providers.storage,
        auth_service=auth_service,
        audit=audit,
        presence=providers.presence,
        inbox=providers.inbox,
    )


def get_phone_service(
    settings: SettingsDep,
    database: RequiredDatabaseDep,
    providers: ProvidersDep,
    limiter: RateLimiterDep,
    audit: AuditLoggerDep,
    auth_service: AuthServiceDep,
) -> PhoneVerificationService:
    return PhoneVerificationService(
        settings=settings,
        database=database,
        delivery=providers.otp,
        inbox=providers.inbox,
        limiter=limiter,
        audit=audit,
        auth_service=auth_service,
    )


def get_profile_service(
    database: RequiredDatabaseDep,
    providers: ProvidersDep,
    limiter: RateLimiterDep,
    audit: AuditLoggerDep,
) -> ProfileService:
    return ProfileService(
        database=database,
        storage=providers.storage,
        limiter=limiter,
        audit=audit,
        presence=providers.presence,
    )


def get_contact_service(
    database: RequiredDatabaseDep,
    providers: ProvidersDep,
    limiter: RateLimiterDep,
    audit: AuditLoggerDep,
) -> ContactService:
    return ContactService(
        database=database,
        storage=providers.storage,
        limiter=limiter,
        audit=audit,
        presence=providers.presence,
    )


ContactServiceDep = Annotated[ContactService, Depends(get_contact_service)]


def get_chat_service(
    database: RequiredDatabaseDep, providers: ProvidersDep, limiter: RateLimiterDep
) -> ChatService:
    return ChatService(
        database=database,
        attachments=providers.attachment_storage,
        avatars=providers.storage,
        limiter=limiter,
        presence=providers.presence,
        hub=providers.realtime,
    )


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
PhoneServiceDep = Annotated[PhoneVerificationService, Depends(get_phone_service)]
ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


# -- authentication ----------------------------------------------------------------------


class AccountLookup(Protocol):
    async def resolve(self, claims: TokenClaims) -> AuthenticatedUser: ...


def get_account_lookup(database: RequiredDatabaseDep) -> AccountLookup:
    return AccountResolver(database)


async def get_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> str:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication is required.")
    return credentials.credentials


AccessTokenDep = Annotated[str, Depends(get_access_token)]


async def get_current_user(
    settings: SettingsDep,
    token: AccessTokenDep,
    lookup: Annotated[AccountLookup, Depends(get_account_lookup)],
) -> AuthenticatedUser:
    """Verify the token, then confirm the session and account in the database.

    The identity comes only from the verified token; user ids in paths or bodies are never
    used as proof of who is calling.
    """
    # In a worker thread: verifying an ES256/RS256 token can fetch the JWKS over the network.
    claims = await run_in_threadpool(decode_access_token, token, settings)
    return await lookup.resolve(claims)


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]


async def require_active_user(user: CurrentUserDep) -> AuthenticatedUser:
    """Email verified (FR-AUTH-002 AC2/AC3)."""
    if user.status != "active":
        raise PermissionDeniedError(
            "Confirm your email address to continue.", code="email_not_verified"
        )
    return user


ActiveUserDep = Annotated[AuthenticatedUser, Depends(require_active_user)]


async def require_admin(user: ActiveUserDep) -> AuthenticatedUser:
    if user.role != "admin":
        raise PermissionDeniedError("You do not have permission to do this.")
    return user


AdminUserDep = Annotated[AuthenticatedUser, Depends(require_admin)]
