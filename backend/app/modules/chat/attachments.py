"""Attachment validation (FR-MSG-010).

The declared content type and file name extension are ignored: the type comes from the file's
own bytes. Images must also decode, and static JPEG, PNG and WebP images are re-encoded from
pixel data so EXIF (including GPS location) is not shared. GIFs keep their animation and are
only checked for validity; PDFs are checked by signature only.
"""

import io
import re
import unicodedata
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_MESSAGE = 5
MAX_SOURCE_PIXELS = 40_000_000

_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
}
_PIL_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}
_UNSAFE_NAME = re.compile(r"[\x00-\x1f\x7f/\\:*?\"<>|]+")


class InvalidAttachmentError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CheckedFile:
    data: bytes
    content_type: str
    extension: str


def sniff_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def safe_file_name(raw: str | None, content_type: str) -> str:
    """Display name only (never a storage path). Keeps the user's name where it is safe."""
    name = unicodedata.normalize("NFC", (raw or "").replace("\\", "/").rsplit("/", 1)[-1])
    name = _UNSAFE_NAME.sub("_", name).strip(" .")
    if not name:
        name = "attachment" + _EXTENSIONS[content_type]
    return name[:255]


def _reencode(data: bytes, content_type: str) -> bytes:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(data)) as probe:
                if _PIL_FORMATS.get(probe.format or "") != content_type:
                    raise InvalidAttachmentError("The file content does not match its type.")
                width, height = probe.size
                if width * height > MAX_SOURCE_PIXELS:
                    raise InvalidAttachmentError("The image dimensions are too large.")
                animated = bool(getattr(probe, "is_animated", False))
                probe.verify()
            if content_type == "image/gif" or animated:
                # Re-encoding would drop the animation; the file has been verified as valid.
                return data
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                image = ImageOps.exif_transpose(source)
        except InvalidAttachmentError:
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise InvalidAttachmentError("The image could not be read.") from exc
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise InvalidAttachmentError("The image dimensions are too large.") from exc

    output = io.BytesIO()
    if content_type == "image/jpeg":
        image.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
    elif content_type == "image/png":
        image.save(output, format="PNG", optimize=True)
    else:
        image.save(output, format="WEBP", quality=90)
    return output.getvalue()


def check_attachment(data: bytes) -> CheckedFile:
    """Validate an upload. Runs CPU-bound image work: call it from a worker thread."""
    if not data:
        raise InvalidAttachmentError("The file is empty.")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise InvalidAttachmentError("Files must be 10 MB or smaller.")
    content_type = sniff_type(data)
    if content_type is None:
        raise InvalidAttachmentError("Use a JPEG, PNG, WebP or GIF image, or a PDF.")
    if content_type != "application/pdf":
        data = _reencode(data, content_type)
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise InvalidAttachmentError("Files must be 10 MB or smaller.")
    return CheckedFile(data=data, content_type=content_type, extension=_EXTENSIONS[content_type])
