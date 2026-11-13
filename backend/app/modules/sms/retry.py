"""Retry timing and eligibility (design section 8.2, FR-SMS-011)."""

import random
from dataclasses import dataclass

from app.integrations.sms.base import FailureClass

JITTER = 0.25
# Only these classes may be sent again automatically.
RETRYABLE: frozenset[FailureClass] = frozenset({"transient"})


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_seconds: float
    cap_seconds: float
    multiplier: float


def is_retryable(failure_class: FailureClass) -> bool:
    return failure_class in RETRYABLE


def delay_seconds(
    policy: RetryPolicy, attempt_number: int, rng: random.Random, retry_after: float | None = None
) -> float:
    """Delay before the attempt that follows `attempt_number`.

    min(cap, base * multiplier^(n-1)) with +-25% jitter from the injected generator, so tests
    can seed it. A longer provider Retry-After wins.
    """
    raw = min(policy.cap_seconds, policy.base_seconds * policy.multiplier ** (attempt_number - 1))
    jittered = raw * (1 + rng.uniform(-JITTER, JITTER))
    return max(jittered, retry_after or 0.0)


def can_retry(policy: RetryPolicy, attempt_number: int, failure_class: FailureClass) -> bool:
    return is_retryable(failure_class) and attempt_number < policy.max_attempts
