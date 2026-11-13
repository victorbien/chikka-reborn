"""Destination number validation (FR-SMS-006). Uses the same library as phone verification."""

from dataclasses import dataclass

import phonenumbers
from phonenumbers import PhoneNumberType

from app.core.exceptions import UnprocessableError

_ALLOWED_TYPES: dict[int, str] = {
    PhoneNumberType.MOBILE: "mobile",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_line_or_mobile",
    PhoneNumberType.FIXED_LINE: "fixed_line",
    PhoneNumberType.VOIP: "voip",
}
# Premium, toll-free, shared-cost and similar numbers are never valid SMS destinations.
_BLOCKED_TYPES = {
    PhoneNumberType.PREMIUM_RATE,
    PhoneNumberType.TOLL_FREE,
    PhoneNumberType.SHARED_COST,
    PhoneNumberType.PAGER,
    PhoneNumberType.UAN,
    PhoneNumberType.VOICEMAIL,
    PhoneNumberType.PERSONAL_NUMBER,
}


@dataclass(frozen=True)
class Destination:
    e164: str
    country_code: str
    number_type: str


def _invalid(
    message: str, code: str = "invalid_phone", field: str = "body.to"
) -> UnprocessableError:
    return UnprocessableError(
        message, code=code, details={"problems": [{"field": field, "reason": code}]}
    )


def parse_destination(raw: str, default_region: str | None = None) -> Destination:
    """Normalise to E.164 and identify country and number type.

    `default_region` (ISO 3166-1 alpha-2, from the country selector) lets users type a local
    format such as 0917 123 4567. Without it the number must start with + and a country code.
    """
    candidate = raw.strip()
    region = default_region.upper() if default_region else None
    if not candidate.startswith("+") and region is None:
        raise _invalid("Enter the number with + and the country code, or pick a country.")
    try:
        parsed = phonenumbers.parse(candidate, None if candidate.startswith("+") else region)
    except phonenumbers.NumberParseException as exc:
        raise _invalid("That phone number is not valid.") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise _invalid("That phone number is not valid.")
    country = phonenumbers.region_code_for_number(parsed)
    if not country or len(country) != 2:
        raise _invalid("That phone number is not valid.")
    number_type = phonenumbers.number_type(parsed)
    if number_type in _BLOCKED_TYPES:
        raise _invalid(
            "Premium-rate and special numbers cannot receive messages.", "number_type_blocked"
        )
    return Destination(
        e164=phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
        country_code=country,
        number_type=_ALLOWED_TYPES.get(number_type, "unknown"),
    )


def region_of(e164: str) -> str | None:
    """Best-effort country of a stored E.164 number. Lenient: inbound senders can be anything."""
    try:
        return phonenumbers.region_code_for_number(phonenumbers.parse(e164, None))
    except phonenumbers.NumberParseException:
        return None


def dial_code_for(country_code: str) -> int:
    return int(phonenumbers.country_code_for_region(country_code.upper()))
