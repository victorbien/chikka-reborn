from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile, status

from app.api.deps import (
    AccountServiceDep,
    ActiveUserDep,
    CurrentUserDep,
    PhoneServiceDep,
    ProfileServiceDep,
    RequestMetaDep,
    SettingsDep,
)
from app.modules.auth.cookies import clear_refresh_cookie
from app.modules.auth.schemas import (
    AccountDeletedResponse,
    DeleteAccountRequest,
    PasswordConfirmation,
    PhoneConfirmRequest,
    PhoneStartRequest,
    PhoneStartResponse,
    PhoneStatusResponse,
    SimulatedSmsMessage,
)
from app.modules.profiles.avatar import MAX_UPLOAD_BYTES
from app.modules.profiles.schemas import (
    AvatarResponse,
    HeartbeatRequest,
    OnboardingRequest,
    PresenceResponse,
    PresenceUpdateRequest,
    ProfileResponse,
    ProfileUpdateRequest,
)
from app.schemas.common import DataResponse, ok

router = APIRouter(prefix="/users/me", tags=["profile"])


@router.get("", summary="Your profile")
async def get_me(user: CurrentUserDep, service: ProfileServiceDep) -> DataResponse[ProfileResponse]:
    return ok(await service.get_me(user))


@router.patch("", summary="Edit your profile")
async def update_me(
    body: ProfileUpdateRequest, user: ActiveUserDep, service: ProfileServiceDep
) -> DataResponse[ProfileResponse]:
    return ok(await service.update_me(user, body))


@router.post("/onboarding", summary="Finish profile setup (username and basics)")
async def complete_onboarding(
    body: OnboardingRequest, user: ActiveUserDep, service: ProfileServiceDep
) -> DataResponse[ProfileResponse]:
    return ok(await service.complete_onboarding(user, body))


@router.delete(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete your account (password and the word DELETE required)",
)
async def delete_me(
    body: DeleteAccountRequest,
    response: Response,
    user: CurrentUserDep,
    service: AccountServiceDep,
    settings: SettingsDep,
    meta: RequestMetaDep,
) -> DataResponse[AccountDeletedResponse]:
    deleted_at = await service.delete_account(user, body.password, meta)
    clear_refresh_cookie(response, settings)
    return ok(
        AccountDeletedResponse(
            message="Your account has been deleted and you have been signed out everywhere.",
            deleted_at=deleted_at,
        )
    )


# -- photo ---------------------------------------------------------------------------------


@router.post("/avatar", summary="Upload a profile photo (JPEG, PNG or WebP, up to 2 MB)")
async def upload_avatar(
    user: ActiveUserDep,
    service: ProfileServiceDep,
    avatar: Annotated[UploadFile, File(description="Image file")],
) -> DataResponse[AvatarResponse]:
    # Read at most one byte past the limit so oversized files never sit fully in memory.
    data = await avatar.read(MAX_UPLOAD_BYTES + 1)
    await avatar.close()
    return ok(AvatarResponse(avatar_url=await service.upload_avatar(user, data)))


@router.delete("/avatar", status_code=status.HTTP_204_NO_CONTENT, summary="Remove your photo")
async def remove_avatar(user: ActiveUserDep, service: ProfileServiceDep) -> Response:
    await service.remove_avatar(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- presence ------------------------------------------------------------------------------


@router.put("/presence", summary="Choose online, away, busy or invisible")
async def set_presence(
    body: PresenceUpdateRequest, user: ActiveUserDep, service: ProfileServiceDep
) -> DataResponse[PresenceResponse]:
    return ok(await service.set_presence(user, body.preference))


@router.post("/presence/heartbeat", summary="Keep presence alive (every 30 seconds)")
async def heartbeat(
    body: HeartbeatRequest, user: ActiveUserDep, service: ProfileServiceDep
) -> DataResponse[PresenceResponse]:
    return ok(await service.heartbeat(user, idle=body.idle))


# -- mobile number -------------------------------------------------------------------------


@router.get("/phone", summary="Your verified mobile number (masked)")
async def phone_status(
    user: ActiveUserDep, service: PhoneServiceDep
) -> DataResponse[PhoneStatusResponse]:
    return ok(await service.status(user))


@router.post("/phone", summary="Send a verification code to a mobile number")
async def start_phone_verification(
    body: PhoneStartRequest, user: ActiveUserDep, service: PhoneServiceDep, meta: RequestMetaDep
) -> DataResponse[PhoneStartResponse]:
    return ok(await service.start(user, body.phone_number, body.password, meta))


@router.post("/phone/verify", summary="Confirm the code sent to the mobile number")
async def confirm_phone_verification(
    body: PhoneConfirmRequest, user: ActiveUserDep, service: PhoneServiceDep, meta: RequestMetaDep
) -> DataResponse[PhoneStatusResponse]:
    return ok(await service.confirm(user, body.phone_number, body.code, meta))


@router.delete("/phone", status_code=status.HTTP_204_NO_CONTENT, summary="Remove your number")
async def remove_phone(
    body: PasswordConfirmation, user: ActiveUserDep, service: PhoneServiceDep, meta: RequestMetaDep
) -> Response:
    await service.remove(user, body.password, meta)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/phone/simulated-inbox",
    summary="SIMULATED codes (simulation mode, non-production only)",
)
async def simulated_inbox(
    user: ActiveUserDep, service: PhoneServiceDep
) -> DataResponse[list[SimulatedSmsMessage]]:
    return ok(service.simulated_inbox(user))
