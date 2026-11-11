import re
import uuid
from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# Accept a caller-supplied ID only if it is short and log-safe.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def new_request_id(candidate: str | None = None) -> str:
    if candidate and _SAFE_REQUEST_ID.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()
