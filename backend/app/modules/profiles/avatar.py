"""Profile photo validation and re-encoding (FR-AUTH-011).

The upload's declared content type is ignored. The bytes are decoded by Pillow, which must
recognise them as JPEG, PNG or WebP. The image is then re-encoded to WebP from pixel data
only, which drops EXIF (including GPS) and any embedded payload.
"""

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_SOURCE_PIXELS = 25_000_000  # guards against decompression bombs
OUTPUT_SIZE = 512
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class InvalidImageError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def process_avatar(data: bytes) -> bytes:
    """Return a square-bounded WebP. Raises InvalidImageError with a user-safe reason."""
    if not data:
        raise InvalidImageError("The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidImageError("The image must be 2 MB or smaller.")

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(data)) as probe:
                image_format = probe.format
                width, height = probe.size
                if image_format not in ALLOWED_FORMATS:
                    raise InvalidImageError("Use a JPEG, PNG or WebP image.")
                if width * height > MAX_SOURCE_PIXELS:
                    raise InvalidImageError("The image dimensions are too large.")
                probe.verify()
            # verify() leaves the image unusable; decode again for real.
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                image = ImageOps.exif_transpose(source)
        except InvalidImageError:
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise InvalidImageError("The file is not a readable image.") from exc
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise InvalidImageError("The image dimensions are too large.") from exc

    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if has_alpha else "RGB")
    image.thumbnail((OUTPUT_SIZE, OUTPUT_SIZE))

    output = io.BytesIO()
    image.save(output, format="WEBP", quality=85, method=4)
    return output.getvalue()
