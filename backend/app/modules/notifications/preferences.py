"""Notification preference rules. Pure functions: no database, no clock.

The database stores only deviations from these defaults (notification_preferences.overrides, keys
like "new_message.email"). Mandatory notices cannot have their in-app copy switched off, and the
database enforces the same list.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Literal, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

NotificationType = Literal[
    "new_message",
    "sms_inbound",
    "sms_delivered",
    "sms_failed",
    "contact_request",
    "contact_accepted",
    "low_balance",
    "system",
    "security",
]
Channel = Literal["in_app", "push", "email"]

TYPES: tuple[NotificationType, ...] = get_args(NotificationType)
CHANNELS: tuple[Channel, ...] = get_args(Channel)

# Failed SMS, system notices and security notices always appear in the app.
MANDATORY_IN_APP: frozenset[str] = frozenset({"sms_failed", "system", "security"})
# Types whose body can reveal what someone wrote. Without "show previews" the body is dropped.
PREVIEW_TYPES: frozenset[str] = frozenset({"new_message", "sms_inbound"})

# "push" means a browser notification while the app is open. Email is off unless it matters
# when you are away from the app.
_PUSH_OFF = frozenset({"sms_delivered", "contact_accepted"})
_EMAIL_ON = frozenset({"system", "security"})

DEFAULTS: dict[str, dict[str, bool]] = {
    kind: {
        "in_app": True,
        "push": kind not in _PUSH_OFF,
        "email": kind in _EMAIL_ON,
    }
    for kind in TYPES
}


def override_key(kind: str, channel: str) -> str:
    return f"{kind}.{channel}"


@dataclass(frozen=True)
class Preferences:
    overrides: dict[str, bool] = field(default_factory=dict)
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    show_previews: bool = False
    low_balance_threshold_units: int = 500
    time_zone: str = "UTC"
    email_disabled: bool = False

    def wants(self, kind: str, channel: str) -> bool:
        if channel == "in_app" and kind in MANDATORY_IN_APP:
            return True
        key = override_key(kind, channel)
        if key in self.overrides:
            return self.overrides[key]
        return DEFAULTS[kind][channel]

    def keeps_body(self, kind: str) -> bool:
        return kind not in PREVIEW_TYPES or self.show_previews

    def is_quiet(self, now: datetime) -> bool:
        return in_quiet_hours(now, self.time_zone, self.quiet_hours_start, self.quiet_hours_end)


def in_quiet_hours(now: datetime, time_zone: str, start: time | None, end: time | None) -> bool:
    """True when `now` in the user's time zone is in [start, end). May wrap midnight."""
    if start is None or end is None or start == end:
        return False
    try:
        zone = ZoneInfo(time_zone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    local = now.astimezone(zone).time().replace(tzinfo=None)
    if start < end:
        return start <= local < end
    return local >= start or local < end


def overrides_for(matrix: dict[str, dict[str, bool]]) -> dict[str, bool]:
    """Reduce a full or partial type -> channel -> bool matrix to deviations from the defaults."""
    overrides: dict[str, bool] = {}
    for kind, channels in matrix.items():
        for channel, enabled in channels.items():
            if enabled != DEFAULTS[kind][channel]:
                overrides[override_key(kind, channel)] = enabled
    return overrides
