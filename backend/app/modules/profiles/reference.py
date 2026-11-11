"""Allowed values for profile fields. Validated server-side; the frontend mirrors them."""

from functools import lru_cache
from zoneinfo import available_timezones

import phonenumbers

# Languages offered in the UI and for AI features (Module K/F). Extend with a migration-free
# config change; the database only checks the BCP 47 shape.
SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {"en", "fil", "ceb", "ilo", "hil", "es", "ar", "zh", "ja", "ko", "id", "ms", "vi", "th"}
)

# Usernames that could impersonate staff or the system.
RESERVED_USERNAMES: frozenset[str] = frozenset(
    {
        "admin",
        "administrator",
        "root",
        "system",
        "support",
        "help",
        "chikka",
        "chikkareborn",
        "official",
        "moderator",
        "mod",
        "staff",
        "security",
        "null",
        "undefined",
        "deleted_user",
    }
)


@lru_cache
def supported_regions() -> frozenset[str]:
    """ISO 3166-1 alpha-2 codes known to libphonenumber."""
    return frozenset(r for r in phonenumbers.SUPPORTED_REGIONS if len(r) == 2)


@lru_cache
def supported_time_zones() -> frozenset[str]:
    return frozenset(available_timezones())
