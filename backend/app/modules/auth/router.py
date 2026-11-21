from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.api.deps import (
    AccessTokenDep,
    AuthServiceDep,
    CurrentUserDep,
    ProvidersDep,
    RequestMetaDep,
    SettingsDep,
)
from app.integrations.auth_provider import AuthSession
from app.modules.auth.cookies import (
    REFRESH_COOKIE,
    clear_refresh_cookie,
    require_csrf_header,
    set_refresh_cookie,
)
from app.modules.auth.schemas import (
    EmailOnlyRequest,
    LoginRequest,
    LogoutRequest,
    RegisterRequest,
    ResetPasswordConfirmRequest,
    SessionInfo,
    SessionTokens,
    TokenHashRequest,
)
from app.schemas.common import DataResponse, MessageData, ok

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue(response: Response, settings: SettingsDep, auth_session: AuthSession) -> SessionTokens:
    set_refresh_cookie(response, settings, auth_session.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return SessionTokens(access_token=auth_session.access_token, expires_in=auth_session.expires_in)


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create an account; a confirmation email follows",
)
async def register(
    body: RegisterRequest, service: AuthServiceDep, meta: RequestMetaDep
) -> DataResponse[MessageData]:
    message = await service.register(
        email=body.email, password=body.password, display_name=body.display_name, meta=meta
    )
    return ok(MessageData(message=message))


@router.post("/login", summary="Sign in with email and password")
async def login(
    body: LoginRequest,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    meta: RequestMetaDep,
) -> DataResponse[SessionTokens]:
    auth_session = await service.login(email=body.email, password=body.password, meta=meta)
    return ok(_issue(response, settings, auth_session))


@router.post(
    "/refresh",
    summary="Exchange the refresh cookie for a new access token",
    dependencies=[Depends(require_csrf_header)],
)
async def refresh(
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    meta: RequestMetaDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> DataResponse[SessionTokens]:
    try:
        auth_session = await service.refresh(refresh_token, meta)
    except Exception:
        clear_refresh_cookie(response, settings)
        raise
    return ok(_issue(response, settings, auth_session))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
async def logout(
    user: CurrentUserDep,
    token: AccessTokenDep,
    service: AuthServiceDep,
    settings: SettingsDep,
    meta: RequestMetaDep,
    providers: ProvidersDep,
    body: LogoutRequest | None = None,
) -> Response:
    scope = (body or LogoutRequest()).scope
    await service.logout(user, token, scope, meta)
    # Live sockets end with the session, not when their access token happens to expire.
    if scope == "global":
        providers.realtime.disconnect_user(user.id)
    else:
        providers.realtime.disconnect_session(user.session_id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response, settings)
    return response


@router.post("/verify-email", summary="Confirm an email address from the emailed link")
async def verify_email(
    body: TokenHashRequest,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    meta: RequestMetaDep,
) -> DataResponse[SessionTokens]:
    auth_session = await service.verify_email(body.token_hash, meta)
    return ok(_issue(response, settings, auth_session))


@router.post("/resend-verification", summary="Send a new confirmation email")
async def resend_verification(
    body: EmailOnlyRequest, service: AuthServiceDep, meta: RequestMetaDep
) -> DataResponse[MessageData]:
    return ok(MessageData(message=await service.resend_verification(body.email, meta)))


@router.post("/reset-password", summary="Email a password reset link")
async def reset_password(
    body: EmailOnlyRequest, service: AuthServiceDep, meta: RequestMetaDep
) -> DataResponse[MessageData]:
    return ok(MessageData(message=await service.request_password_reset(body.email, meta)))


@router.post("/reset-password/confirm", summary="Set a new password from the emailed link")
async def reset_password_confirm(
    body: ResetPasswordConfirmRequest,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    meta: RequestMetaDep,
) -> DataResponse[MessageData]:
    await service.confirm_password_reset(body.token_hash, body.new_password, meta)
    clear_refresh_cookie(response, settings)
    return ok(MessageData(message="Your password has been changed. Please sign in."))


@router.get("/sessions", summary="List your active sessions")
async def list_sessions(
    user: CurrentUserDep, service: AuthServiceDep
) -> DataResponse[list[SessionInfo]]:
    return ok(await service.list_sessions(user))


@router.delete(
    "/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a session"
)
async def revoke_session(
    session_id: UUID, user: CurrentUserDep, service: AuthServiceDep, meta: RequestMetaDep
) -> Response:
    await service.revoke_session(user, session_id, meta)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/revoke-others", summary="Sign out every other device")
async def revoke_other_sessions(
    user: CurrentUserDep, service: AuthServiceDep, meta: RequestMetaDep
) -> DataResponse[MessageData]:
    count = await service.revoke_other_sessions(user, meta)
    noun = "session" if count == 1 else "sessions"
    return ok(MessageData(message=f"Signed out {count} other {noun}."))
