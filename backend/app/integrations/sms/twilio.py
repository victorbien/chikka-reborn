"""TwilioSmsProvider (live). Talks to Twilio's REST API with httpx; no vendor SDK.

Credentials come from the environment only. They are used for HTTP basic auth and webhook
signature checks and are never logged, returned or stored.

Items to verify against the Twilio account before enabling live sending are listed in
docs/deployment/sms-live-activation.md.
"""

import base64
import hashlib
import hmac
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl
from uuid import UUID

import httpx

from app.integrations.sms.base import (
    DeliveryStatus,
    InboundSmsEvent,
    ProviderCountryInfo,
    ProviderError,
    ProviderStatusEvent,
    ProviderStatusSnapshot,
    SendRequest,
    SendResult,
    SmsMode,
    SmsProvider,
    WebhookError,
)
from app.integrations.sms.errors import classify_twilio_code

API_BASE = "https://api.twilio.com"
PRICING_BASE = "https://pricing.twilio.com"
SIGNATURE_HEADER = "x-twilio-signature"

_STATUS_MAP: dict[str, DeliveryStatus] = {
    "accepted": "accepted",
    "scheduled": "accepted",
    "queued": "accepted",
    "sending": "accepted",
    "sent": "sent",
    "delivered": "delivered",
    "undelivered": "undelivered",
    "failed": "failed",
    "canceled": "failed",
}


def map_twilio_status(status: str) -> DeliveryStatus | None:
    """Twilio status -> platform status. Unknown values return None: they are recorded but
    never change a message."""
    return _STATUS_MAP.get(status.lower())


def compute_signature(auth_token: str, url: str, params: Mapping[str, list[str]]) -> str:
    """Twilio's scheme: HMAC-SHA1 over the URL plus every POST parameter, sorted by name."""
    payload = url
    for key in sorted(params):
        for value in sorted(params[key]):
            payload += key + value
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def parse_form(raw_body: bytes) -> dict[str, list[str]]:
    try:
        pairs = parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True, strict_parsing=False)
    except UnicodeDecodeError as exc:
        raise WebhookError("webhook body is not valid UTF-8") from exc
    grouped: dict[str, list[str]] = {}
    for key, value in pairs:
        grouped.setdefault(key, []).append(value)
    return grouped


def _first(form: Mapping[str, list[str]], key: str) -> str | None:
    values = form.get(key)
    return values[0] if values else None


class TwilioSmsProvider(SmsProvider):
    name = "twilio"
    mode: SmsMode = "live"

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not account_sid or not auth_token:
            raise ProviderError(
                "configuration", "twilio_credentials_missing", "Twilio credentials are missing"
            )
        self._sid = account_sid
        self._token = auth_token
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            auth=httpx.BasicAuth(account_sid, auth_token),
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # -- outbound --------------------------------------------------------------------------

    async def send_message(self, request: SendRequest) -> SendResult:
        data = {"To": request.to, "From": request.sender, "Body": request.body}
        if request.status_callback_url:
            data["StatusCallback"] = request.status_callback_url
        url = f"{API_BASE}/2010-04-01/Accounts/{self._sid}/Messages.json"
        response = await self._request("POST", url, data=data)
        payload = self._json(response)
        sid = payload.get("sid")
        if response.status_code not in (200, 201) or not isinstance(sid, str) or not sid:
            raise self._error_from(response, payload)
        status = str(payload.get("status", "queued"))
        raw_segments = str(payload.get("num_segments", ""))
        segments = int(raw_segments) if raw_segments.isdigit() else None
        return SendResult(
            provider_message_id=sid,
            provider_status=status,
            mapped_status=map_twilio_status(status) or "accepted",
            segments_reported=segments,
            response={
                "sid": sid,
                "status": status,
                "num_segments": segments,
                "error_code": str(payload["error_code"]) if payload.get("error_code") else None,
            },
        )

    async def get_message_status(self, provider_message_id: str) -> ProviderStatusSnapshot:
        url = f"{API_BASE}/2010-04-01/Accounts/{self._sid}/Messages/{provider_message_id}.json"
        response = await self._request("GET", url)
        payload = self._json(response)
        if response.status_code != 200:
            raise self._error_from(response, payload)
        status = str(payload.get("status", ""))
        mapped = map_twilio_status(status)
        if mapped is None:
            raise ProviderError("permanent", "unknown_status", "Unrecognised provider status")
        code = payload.get("error_code")
        return ProviderStatusSnapshot(
            provider_message_id=provider_message_id,
            provider_status=status,
            mapped_status=mapped,
            error_code=str(code) if code else None,
        )

    async def _request(
        self, method: str, url: str, *, data: dict[str, str] | None = None
    ) -> httpx.Response:
        try:
            return await self._client.request(method, url, data=data)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            # The request never left: a retry cannot duplicate the message.
            raise ProviderError(
                "transient", "network_error", "Could not reach the provider"
            ) from exc
        except httpx.TransportError as exc:
            # The request may have been processed: do not blindly resend.
            raise ProviderError(
                "ambiguous", "outcome_unknown", "The provider did not answer in time"
            ) from exc

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _error_from(response: httpx.Response, payload: Mapping[str, Any]) -> ProviderError:
        status = response.status_code
        code = str(payload["code"]) if payload.get("code") else None
        if status in (401, 403):
            return ProviderError(
                "configuration",
                code or "unauthorised",
                "The provider rejected our credentials",
                http_status=status,
            )
        if status == 429 or status >= 500:
            retry_after: float | None = None
            header = response.headers.get("retry-after")
            if header and header.replace(".", "", 1).isdigit():
                retry_after = float(header)
            return ProviderError(
                "transient",
                code or f"http_{status}",
                "The provider is temporarily unavailable",
                http_status=status,
                retry_after=retry_after,
            )
        return ProviderError(
            classify_twilio_code(code),
            code or f"http_{status}",
            "The provider rejected the message",
            http_status=status,
        )

    # -- webhooks --------------------------------------------------------------------------

    async def validate_webhook(self, raw_body: bytes, headers: Mapping[str, str], url: str) -> bool:
        lowered = {k.lower(): v for k, v in headers.items()}
        provided = lowered.get(SIGNATURE_HEADER)
        if not provided:
            return False
        try:
            form = parse_form(raw_body)
        except WebhookError:
            return False
        expected = compute_signature(self._token, url, form)
        return hmac.compare_digest(provided.encode(), expected.encode())

    async def parse_inbound_message(
        self, raw_body: bytes, headers: Mapping[str, str]
    ) -> InboundSmsEvent:
        form = parse_form(raw_body)
        sid, sender, recipient = (_first(form, k) for k in ("MessageSid", "From", "To"))
        if not sid or not sender or not recipient:
            raise WebhookError("inbound payload is missing MessageSid, From or To")
        media = _first(form, "NumMedia") or "0"
        return InboundSmsEvent(
            provider_message_id=sid,
            from_phone=sender,
            to_number=recipient,
            body=_first(form, "Body") or "",
            received_at=datetime.now(UTC),
            dedupe_key=sid,
            media_count=int(media) if media.isdigit() else 0,
        )

    async def parse_status_callback(
        self, raw_body: bytes, headers: Mapping[str, str], query: Mapping[str, str]
    ) -> ProviderStatusEvent:
        form = parse_form(raw_body)
        sid = _first(form, "MessageSid") or _first(form, "SmsSid")
        status = _first(form, "MessageStatus") or _first(form, "SmsStatus")
        if not sid or not status:
            raise WebhookError("status payload is missing MessageSid or MessageStatus")
        correlation: UUID | None = None
        raw_correlation = query.get("sms_id")
        if raw_correlation:
            try:
                correlation = UUID(raw_correlation)
            except ValueError:
                correlation = None
        return ProviderStatusEvent(
            provider_message_id=sid,
            provider_status=status,
            mapped_status=map_twilio_status(status),
            error_code=_first(form, "ErrorCode") or None,
            occurred_at=None,
            dedupe_key=f"{sid}:{status.lower()}",
            correlation_id=correlation,
        )

    # -- capabilities ----------------------------------------------------------------------

    async def get_country_capabilities(self, country_code: str) -> ProviderCountryInfo:
        """Pricing for the destination as Twilio reports it. A price is not permission:
        geo permissions and sender registration are checked in the platform configuration."""
        iso = country_code.upper()
        response = await self._request("GET", f"{PRICING_BASE}/v1/Messaging/Countries/{iso}")
        payload = self._json(response)
        if response.status_code != 200:
            raise self._error_from(response, payload)
        prices: list[Decimal] = []
        for carrier in payload.get("outbound_sms_prices", []) or []:
            for price in carrier.get("prices", []) or []:
                if price.get("number_type") == "mobile":
                    try:
                        prices.append(Decimal(str(price["current_price"])))
                    except (KeyError, InvalidOperation):
                        continue
        return ProviderCountryInfo(
            country_code=iso,
            source="twilio_pricing",
            outbound_price_per_segment=max(prices) if prices else None,
            currency=payload.get("price_unit"),
            inbound_supported=None,
            notes="Reported pricing only. Two-way support and sender registration must be "
            "verified with the provider.",
        )
