"""Failure classification (design section 8). Unknown codes are permanent: no repeat sends.

The Twilio table must be reviewed against Twilio's current error catalogue before live mode
(docs/deployment/sms-live-activation.md).
"""

from app.integrations.sms.base import FailureClass

# Twilio error code -> (failure class, short reason that is safe to show to the sender).
TWILIO_ERRORS: dict[str, tuple[FailureClass, str]] = {
    "21211": ("permanent", "The phone number is not valid."),
    "21214": ("permanent", "The phone number cannot receive SMS."),
    "21408": ("permanent", "Sending to this country is not enabled."),
    "21610": ("permanent", "The recipient has opted out of messages."),
    "21612": ("configuration", "The sender cannot reach this destination."),
    "21614": ("permanent", "The number is not a mobile number that can receive SMS."),
    "21606": ("configuration", "The sender number is not enabled for SMS."),
    "21608": ("configuration", "The sender is not approved yet."),
    "20003": ("configuration", "The SMS account could not be authenticated."),
    "20429": ("transient", "The provider is busy. We will try again."),
    "30001": ("transient", "The message queue was full. We will try again."),
    "30002": ("configuration", "The SMS account is suspended."),
    "30003": ("permanent", "The recipient's phone is unreachable or switched off."),
    "30004": ("permanent", "The recipient blocked the message."),
    "30005": ("permanent", "The recipient number is unknown or inactive."),
    "30006": ("permanent", "The number is a landline or cannot be reached."),
    "30007": ("permanent", "The carrier filtered the message."),
    "30008": ("permanent", "The carrier could not deliver the message."),
    "30009": ("transient", "Part of the message was missing. We will try again."),
    "30010": ("permanent", "The message expired before it could be delivered."),
}

OPT_OUT_CODES = frozenset({"21610"})
GENERIC_REASON = "The message could not be delivered."


def classify_twilio_code(code: str | None) -> FailureClass:
    if code is None:
        return "permanent"
    return TWILIO_ERRORS.get(code, ("permanent", GENERIC_REASON))[0]


def reason_for_code(code: str | None) -> str:
    """User-readable reason. Provider error text is never shown to users."""
    if code is None:
        return GENERIC_REASON
    return TWILIO_ERRORS.get(code, ("permanent", GENERIC_REASON))[1]


# Mock-only codes share the table shape so the UI path is identical in simulation.
SIMULATED_REASONS: dict[str, str] = {
    "SIM-FAILED": "Simulated failure: the provider reported the message as failed.",
    "SIM-UNDELIVERED": "Simulated failure: the carrier did not deliver the message.",
    "SIM-INVALID": "The phone number is not valid.",
    "SIM-TRANSIENT": "The provider is busy. We will try again.",
    "SIM-UNAVAILABLE": "The provider is busy. We will try again.",
}


# Platform-side failure codes (not provider codes).
SYSTEM_REASONS: dict[str, str] = {
    "retries_exhausted": "We couldn't reach the SMS provider after several tries.",
    "outcome_unknown": "We couldn't confirm whether this message was sent.",
    "queue_expired": "The message waited too long to be sent.",
    "no_sender": "No sender number was available for this message.",
    "network_error": "We couldn't reach the SMS provider.",
}


def reason_for_any(code: str | None) -> str:
    if code is not None and code in SIMULATED_REASONS:
        return SIMULATED_REASONS[code]
    if code is not None and code in SYSTEM_REASONS:
        return SYSTEM_REASONS[code]
    return reason_for_code(code)
