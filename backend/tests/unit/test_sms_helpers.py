import random
from decimal import Decimal

import pytest

from app.core.exceptions import UnprocessableError
from app.modules.sms.capabilities import Capability, estimate_cost, evaluate
from app.modules.sms.numbers import parse_destination
from app.modules.sms.optout import classify_keyword
from app.modules.sms.retry import RetryPolicy, can_retry, delay_seconds
from app.modules.sms.segments import analyse

# Shared with frontend/src/lib/sms.test.ts: (body, encoding, units, segments)
VECTORS = [
    ("", "gsm7", 0, 0),
    ("Hello", "gsm7", 5, 1),
    ("a" * 160, "gsm7", 160, 1),
    ("a" * 161, "gsm7", 161, 2),
    ("a" * 306, "gsm7", 306, 2),
    ("a" * 307, "gsm7", 307, 3),
    ("{" * 80, "gsm7", 160, 1),
    ("{" * 81, "gsm7", 162, 2),
    ("Kumusta ka, Nanay?", "gsm7", 18, 1),
    ("é" * 70, "gsm7", 70, 1),
    ("日本語", "ucs2", 3, 1),
    ("ñ" * 70 + "😀", "ucs2", 72, 2),
    ("字" * 70, "ucs2", 70, 1),
    ("字" * 71, "ucs2", 71, 2),
    ("字" * 134, "ucs2", 134, 2),
    ("字" * 135, "ucs2", 135, 3),
    ("Hi 😀", "ucs2", 5, 1),
]


@pytest.mark.parametrize(("body", "encoding", "units", "segments"), VECTORS)
def test_segment_vectors(body: str, encoding: str, units: int, segments: int) -> None:
    info = analyse(body)
    assert (info.encoding, info.units, info.segments) == (encoding, units, segments)


def capability(**overrides: object) -> Capability:
    values: dict[str, object] = {
        "country_code": "SG",
        "country_name": "Singapore",
        "outbound_support": "supported",
        "inbound_support": "supported",
        "alphanumeric_sender_allowed": False,
        "registered_sender_required": False,
        "registered_sender_status": "not_required",
        "content_restrictions": None,
        "credit_multiplier": Decimal(1),
        "max_segments": 10,
        "notes": None,
        "price_units_per_segment": 100,
        "supported_number_types": ("mobile", "fixed_line_or_mobile"),
        "consent_required": True,
        "provider_settings": {},
    }
    values.update(overrides)
    return Capability(**values)  # type: ignore[arg-type]


def test_unknown_country_is_unavailable_in_both_modes() -> None:
    for live in (True, False):
        verdict = evaluate(None, number_type="mobile", live=live)
        assert not verdict.allowed
        assert verdict.reason_code == "country_unsupported"


def test_unverified_route_is_unavailable_for_live_but_usable_in_simulation() -> None:
    cap = capability(outbound_support="requires_verification")
    live = evaluate(cap, number_type="mobile", live=True)
    assert live.availability == "unavailable"
    assert live.reason_code == "route_unverified"
    simulated = evaluate(cap, number_type="mobile", live=False)
    assert simulated.availability == "simulation_only"
    assert any("not verified" in w for w in simulated.warnings)


def test_philippines_style_registration_blocks_live_only() -> None:
    cap = capability(
        country_code="PH",
        country_name="Philippines",
        outbound_support="requires_verification",
        inbound_support="requires_verification",
        registered_sender_required=True,
        registered_sender_status="not_registered",
    )
    assert evaluate(cap, number_type="mobile", live=True).reason_code == "route_unverified"
    sim = evaluate(cap, number_type="mobile", live=False)
    assert sim.allowed
    assert sim.replies == "unverified"
    assert any("registered sender" in w for w in sim.warnings)


def test_live_needs_registration_and_pricing() -> None:
    registered = capability(registered_sender_required=True, registered_sender_status="pending")
    assert evaluate(registered, number_type="mobile", live=True).reason_code == (
        "sender_registration_required"
    )
    unpriced = capability(price_units_per_segment=None)
    assert evaluate(unpriced, number_type="mobile", live=True).reason_code == (
        "pricing_not_configured"
    )
    assert evaluate(capability(), number_type="mobile", live=True).availability == "available"


def test_number_type_and_unsupported_outbound_are_blocked() -> None:
    assert evaluate(capability(), number_type="fixed_line", live=False).reason_code == (
        "number_type_unsupported"
    )
    assert not evaluate(
        capability(outbound_support="unsupported"), number_type="mobile", live=False
    ).allowed


def test_replies_are_never_promised_when_unsupported() -> None:
    verdict = evaluate(capability(inbound_support="unsupported"), number_type="mobile", live=True)
    assert verdict.replies == "unsupported"
    assert any("Replies are not supported" in w for w in verdict.warnings)


def test_cost_estimate_sources() -> None:
    cap = capability(credit_multiplier=Decimal("1.5"))
    assert estimate_cost(cap, 2, live=True, demo_units_per_segment=50).units == 300
    unpriced = capability(price_units_per_segment=None)
    assert estimate_cost(unpriced, 2, live=True, demo_units_per_segment=50).source == "unavailable"
    demo = estimate_cost(unpriced, 2, live=False, demo_units_per_segment=50)
    assert (demo.units, demo.source) == (100, "demo_default")
    assert estimate_cost(None, 1, live=False, demo_units_per_segment=50).units is None


@pytest.mark.parametrize(
    ("raw", "region", "expected"),
    [
        ("+63 917 123 4567", None, ("+639171234567", "PH")),
        ("0917 123 4567", "PH", ("+639171234567", "PH")),
        ("+12025550142", None, ("+12025550142", "US")),
    ],
)
def test_parse_destination(raw: str, region: str | None, expected: tuple[str, str]) -> None:
    destination = parse_destination(raw, region)
    assert (destination.e164, destination.country_code) == expected


@pytest.mark.parametrize(
    ("raw", "region"),
    [("09171234567", None), ("+63123", None), ("not a number", "PH"), ("+18005550199", None)],
)
def test_parse_destination_rejects(raw: str, region: str | None) -> None:
    with pytest.raises(UnprocessableError):
        parse_destination(raw, region)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("STOP", ("opt_out", "stop")),
        ("  stopall \n", ("opt_out", "stopall")),
        ("Unsubscribe", ("opt_out", "unsubscribe")),
        ("start", ("opt_in", "start")),
        ("please stop by later", None),
        ("stopping", None),
        ("yes", None),
        ("", None),
    ],
)
def test_keywords_match_whole_message_only(body: str, expected: tuple[str, str] | None) -> None:
    assert classify_keyword(body) == expected


def test_retry_delay_is_exponential_capped_and_seeded() -> None:
    policy = RetryPolicy(max_attempts=4, base_seconds=5, cap_seconds=30, multiplier=2)
    first = [delay_seconds(policy, n, random.Random(1)) for n in (1, 2, 3, 4, 5)]
    assert first == [delay_seconds(policy, n, random.Random(1)) for n in (1, 2, 3, 4, 5)]
    for n, value in zip((1, 2, 3, 4, 5), first, strict=True):
        raw = min(30, 5 * 2 ** (n - 1))
        assert raw * 0.75 <= value <= raw * 1.25
    assert delay_seconds(policy, 1, random.Random(1), retry_after=120) == 120


def test_only_transient_failures_below_the_limit_retry() -> None:
    policy = RetryPolicy(max_attempts=3, base_seconds=1, cap_seconds=1, multiplier=1)
    assert can_retry(policy, 1, "transient")
    assert can_retry(policy, 2, "transient")
    assert not can_retry(policy, 3, "transient")
    for failure in ("permanent", "ambiguous", "configuration", "policy"):
        assert not can_retry(policy, 1, failure)  # type: ignore[arg-type]
