import io

import pytest
from PIL import Image

from app.core.privacy import ip_prefix, mask_phone
from app.core.sanitize import clean_text
from app.modules.auth.schemas import validate_password
from app.modules.auth.service import describe_user_agent
from app.modules.profiles.avatar import InvalidImageError, process_avatar
from app.modules.profiles.presence import PresenceRegistry
from app.modules.profiles.schemas import ProfileUpdateRequest, validate_username


def _image(fmt: str, size: tuple[int, int] = (64, 64), mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, (1, 2, 3, 4)[: len(mode)]).save(buffer, format=fmt)
    return buffer.getvalue()


# -- text and privacy ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  hello  ", "hello"),
        ("<b>bold</b> text", "bold text"),
        ("&lt;script&gt;alert(1)&lt;/script&gt;hi", "alert(1)hi"),
        ("tab\x00null\x07bell", "tabnullbell"),
        ("Salamat po 🙏", "Salamat po 🙏"),
    ],
)
def test_clean_text(raw: str, expected: str) -> None:
    assert clean_text(raw) == expected


def test_mask_phone_matches_the_logging_policy() -> None:
    assert mask_phone("+639171234567") == "+63****4567"
    assert mask_phone("+1234") == "****"


def test_ip_prefix_is_coarse() -> None:
    assert ip_prefix("203.0.113.77") == "203.0.113.0/24"
    assert ip_prefix("2001:db8:1234:5678::1") == "2001:db8:1234::/48"
    assert ip_prefix("not-an-ip") is None
    assert ip_prefix(None) is None


# -- validation ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "password", ["Short1A", "alllowercase1", "ALLUPPERCASE1", "NoDigitsHere", "Ä" * 37 + "a1"]
)
def test_weak_passwords_are_rejected(password: str) -> None:
    with pytest.raises(ValueError):
        validate_password(password)


def test_strong_password_is_accepted() -> None:
    assert validate_password("Correct-Horse-7") == "Correct-Horse-7"


@pytest.mark.parametrize("username", ["abc", "Mari_2026", "a" * 20])
def test_valid_usernames(username: str) -> None:
    assert validate_username(username) == username


@pytest.mark.parametrize("username", ["ab", "a" * 21, "has space", "dash-name", "ADMIN", "Chikka"])
def test_invalid_usernames(username: str) -> None:
    with pytest.raises(ValueError):
        validate_username(username)


def test_profile_update_only_reports_fields_that_were_sent() -> None:
    request = ProfileUpdateRequest(bio="  hi  ")
    assert request.model_dump(exclude_unset=True) == {"bio": "hi"}


def test_empty_bio_clears_it() -> None:
    assert ProfileUpdateRequest(bio="   ").bio is None


# -- avatar --------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_supported_images_become_webp(fmt: str) -> None:
    output = process_avatar(_image(fmt, (1024, 512)))
    with Image.open(io.BytesIO(output)) as image:
        assert image.format == "WEBP"
        assert image.size == (512, 256)


def test_transparency_is_kept() -> None:
    output = process_avatar(_image("PNG", mode="RGBA"))
    with Image.open(io.BytesIO(output)) as image:
        assert image.mode == "RGBA"


def test_exif_including_location_is_removed() -> None:
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (14.0, 35.0, 0.0)}  # GPS IFD
    exif[0x010F] = "FakeCameraMaker"
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40)).save(buffer, format="JPEG", exif=exif)
    with Image.open(io.BytesIO(process_avatar(buffer.getvalue()))) as image:
        assert not image.getexif()


@pytest.mark.parametrize(
    "data",
    [b"", b"GIF89a not really", b"\x89PNG\r\n\x1a\n" + b"\x00" * 30, _image("GIF"), _image("BMP")],
)
def test_unsupported_or_corrupt_files_are_rejected(data: bytes) -> None:
    with pytest.raises(InvalidImageError):
        process_avatar(data)


def test_oversized_upload_is_rejected_before_decoding() -> None:
    with pytest.raises(InvalidImageError, match="2 MB"):
        process_avatar(b"0" * (2 * 1024 * 1024 + 1))


def test_decompression_bomb_is_rejected() -> None:
    buffer = io.BytesIO()
    Image.new("1", (6000, 6000)).save(buffer, format="PNG")  # tiny file, 36M pixels
    with pytest.raises(InvalidImageError, match="dimensions"):
        process_avatar(buffer.getvalue())


# -- presence ------------------------------------------------------------------------------


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_presence_transitions() -> None:
    clock = _Clock()
    registry = PresenceRegistry(clock)
    assert registry.status("u", "online") == "offline"

    assert registry.heartbeat("u", idle=False) is True
    assert registry.status("u", "online") == "online"
    assert registry.status("u", "busy") == "busy"

    clock.now += 30
    assert registry.heartbeat("u", idle=True) is False  # last_seen persisted at most once a minute
    assert registry.status("u", "online") == "away"

    clock.now += 61
    assert registry.status("u", "online") == "offline"
    assert registry.heartbeat("u", idle=False) is True


def test_invisible_looks_offline_to_others() -> None:
    registry = PresenceRegistry(_Clock())
    registry.heartbeat("u", idle=False)
    assert registry.status("u", "invisible") == "invisible"
    assert PresenceRegistry.as_seen_by_others("invisible") == "offline"
    registry.clear("u")
    assert registry.status("u", "online") == "offline"


def test_user_agent_is_summarised() -> None:
    assert (
        describe_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1")
        == "Safari on iPhone"
    )
    assert describe_user_agent(None) == "Unknown device"
