"""Country capability policy (FR-SMS-007, FR-ADMIN-005). The only reader of capability rules.

Rules, in order of strictness:
* No row for the country, or outbound "unsupported": blocked in every mode.
* Live mode: only a route marked "supported" (which the database allows only with recorded
  verification), with the sender registered when registration is required and pricing configured.
  Anything unverified is unavailable. This is the "unverified routes are unavailable for live"
  rule.
* Simulation: unverified routes may be tried so demos work, but they are flagged and the reason
  is shown. Nothing here is evidence that a real carrier route works.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal
from uuid import UUID

Availability = Literal["available", "simulation_only", "unavailable"]
Replies = Literal["supported", "unverified", "unsupported"]


@dataclass(frozen=True)
class Capability:
    country_code: str
    country_name: str
    outbound_support: str
    inbound_support: str
    alphanumeric_sender_allowed: bool
    registered_sender_required: bool
    registered_sender_status: str
    content_restrictions: str | None
    credit_multiplier: Decimal
    max_segments: int
    notes: str | None
    price_units_per_segment: int | None
    supported_number_types: tuple[str, ...]
    consent_required: bool
    provider_settings: dict[str, Any]
    id: UUID | None = None
    version: int = 1
    verified: bool = False


@dataclass(frozen=True)
class Verdict:
    availability: Availability
    reason_code: str | None = None
    reason: str | None = None
    replies: Replies = "unsupported"
    warnings: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.availability != "unavailable"


def _blocked(code: str, reason: str, replies: Replies = "unsupported") -> Verdict:
    return Verdict("unavailable", code, reason, replies)


def evaluate(capability: Capability | None, *, number_type: str, live: bool) -> Verdict:
    if capability is None:
        return _blocked("country_unsupported", "We can't send SMS to this country yet.")
    replies: Replies = "unsupported"
    if capability.inbound_support == "supported":
        replies = "supported"
    elif capability.inbound_support == "requires_verification":
        replies = "unverified"

    if capability.outbound_support == "unsupported":
        return _blocked(
            "country_unsupported", f"SMS to {capability.country_name} is not supported.", replies
        )
    if number_type not in capability.supported_number_types:
        return _blocked(
            "number_type_unsupported",
            "This kind of number can't receive SMS from us in this country.",
            replies,
        )

    warnings: list[str] = []
    registration_missing = (
        capability.registered_sender_required
        and capability.registered_sender_status != "registered"
    )
    unverified = capability.outbound_support != "supported"

    if live:
        if unverified:
            return _blocked(
                "route_unverified",
                f"Live SMS to {capability.country_name} has not been verified with the provider.",
                replies,
            )
        if registration_missing:
            return _blocked(
                "sender_registration_required",
                f"A registered sender is required for {capability.country_name} "
                "and is not approved yet.",
                replies,
            )
        if capability.price_units_per_segment is None:
            return _blocked(
                "pricing_not_configured",
                "Pricing for this destination is not configured.",
                replies,
            )
    else:
        if unverified:
            warnings.append(
                f"Simulation only: the route to {capability.country_name} "
                "is not verified for live SMS."
            )
        if registration_missing:
            warnings.append(
                "A registered sender is required for live messages here and is not approved yet."
            )

    if replies == "unsupported":
        warnings.append("Replies are not supported for this destination.")
    elif replies == "unverified":
        warnings.append("Replies depend on the carrier and route and are not guaranteed.")
    if capability.content_restrictions:
        warnings.append(capability.content_restrictions)

    availability: Availability = (
        "simulation_only" if (unverified or registration_missing) and not live else "available"
    )
    return Verdict(availability, replies=replies, warnings=warnings)


@dataclass(frozen=True)
class CostEstimate:
    units: int | None
    source: Literal["configured", "demo_default", "unavailable"]

    @property
    def credits(self) -> Decimal | None:
        return None if self.units is None else Decimal(self.units) / 100


def estimate_cost(
    capability: Capability | None, segments: int, *, live: bool, demo_units_per_segment: int | None
) -> CostEstimate:
    """Units (credits x 100) = segments x per-segment price x country multiplier."""
    if capability is None:
        return CostEstimate(None, "unavailable")
    price = capability.price_units_per_segment
    source: Literal["configured", "demo_default", "unavailable"] = "configured"
    if price is None:
        if live or demo_units_per_segment is None:
            return CostEstimate(None, "unavailable")
        price, source = demo_units_per_segment, "demo_default"
    total = (Decimal(price) * segments * capability.credit_multiplier).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    return CostEstimate(int(total), source)
