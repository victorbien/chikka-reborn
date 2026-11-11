import html
import re
import unicodedata

_TAG = re.compile(r"<[^>]*>")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: str) -> str:
    """Plain-text normalisation for user-supplied profile text.

    Strips HTML tags and control characters. Output is still escaped on render by React;
    this keeps markup out of storage (FR-AUTH-007 AC2).
    """
    text = unicodedata.normalize("NFC", value)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = _TAG.sub("", text)  # tags that only appeared after unescaping
    text = _CONTROL.sub("", text)
    return text.strip()
