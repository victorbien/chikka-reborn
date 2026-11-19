"""Object-path rules for private storage buckets.

`profiles.avatar_path` is a value a client can influence, so it is never trusted as a storage
path. The backend only ever writes `<user_id>/<32 hex characters>.webp`; anything else is
treated as "no avatar", so a crafted path cannot sign or delete another object (for example
`../message-attachments/...` once the HTTP client normalises the dot segments).
"""

import logging
import re
from uuid import UUID

logger = logging.getLogger(__name__)

_AVATAR_FILE = re.compile(r"[0-9a-f]{32}\.webp")


def avatar_path_for(owner_id: UUID, file_id: str) -> str:
    return f"{owner_id}/{file_id}.webp"


def owned_avatar_path(owner_id: UUID, path: str | None) -> str | None:
    """Return `path` only when it is a well-formed avatar path inside `owner_id`'s folder."""
    if not path:
        return None
    folder, separator, name = path.partition("/")
    if separator and folder == str(owner_id) and _AVATAR_FILE.fullmatch(name):
        return path
    logger.warning("ignored malformed avatar path", extra={"owner_id": str(owner_id)})
    return None


def is_safe_object_path(path: str) -> bool:
    """Defence in depth for every storage call: no empty, relative or dot segments."""
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        return False
    return all(segment not in ("", ".", "..") for segment in path.split("/"))
