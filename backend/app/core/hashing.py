import hashlib
import hmac
import secrets

from app.core.config import Settings

# Dev/test fallback so the app starts without configuration. It changes on every process
# start, so it is never accepted in staging or production (Settings requires APP_SECRET_KEY).
_EPHEMERAL_KEY = secrets.token_bytes(32)


def _key(settings: Settings) -> bytes:
    if settings.app_secret_key is not None:
        return settings.app_secret_key.get_secret_value().encode()
    return _EPHEMERAL_KEY


def keyed_hash(settings: Settings, purpose: str, value: str) -> str:
    """HMAC-SHA256 of value, domain-separated by purpose. Used for rate-limit subjects and OTPs."""
    digest = hmac.new(_key(settings), f"{purpose}:{value}".encode(), hashlib.sha256)
    return digest.hexdigest()


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())
