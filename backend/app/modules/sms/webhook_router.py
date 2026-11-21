"""Provider webhooks. Authenticated by signature, not by JWT (FR-SMSRECV-002)."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import SmsGatewayDep
from app.core.config import Settings
from app.core.exceptions import NotFoundError, PayloadTooLargeError

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def signed_url(settings: Settings, request: Request) -> str:
    """The exact URL the provider signed. Built from configuration, never from request
    headers, so a spoofed Host header cannot change what is verified."""
    path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    base = settings.sms_public_base_url
    return f"{base.rstrip('/')}{path}" if base else str(request.url)


async def _handle(provider: str, kind: str, request: Request, gateway: SmsGatewayDep) -> None:
    # The webhook of a provider that is not running is not served: the mock endpoint does
    # not exist in live mode and vice versa.
    if provider != gateway.provider.name:
        raise NotFoundError("Resource not found.")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > 64 * 1024:
        raise PayloadTooLargeError("Payload too large.")
    raw = await request.body()
    settings: Settings = request.app.state.settings
    await gateway.webhooks.handle(
        kind=kind,
        raw_body=raw,
        headers=dict(request.headers),
        url=signed_url(settings, request),
        query=dict(request.query_params),
        ip=request.client.host if request.client else None,
    )


@router.post("/{provider}/inbound", summary="Inbound SMS from a provider")
async def inbound(provider: str, request: Request, gateway: SmsGatewayDep) -> Response:
    await _handle(provider, "inbound", request, gateway)
    return Response(content=_EMPTY_TWIML, media_type="text/xml")


@router.post("/{provider}/status", summary="Delivery status callback from a provider")
async def status_callback(provider: str, request: Request, gateway: SmsGatewayDep) -> JSONResponse:
    await _handle(provider, "status", request, gateway)
    return JSONResponse({"received": True})
