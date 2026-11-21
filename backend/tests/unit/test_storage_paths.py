"""SEC-001: a client-influenced avatar path must never reach another object or bucket."""

from uuid import UUID

import httpx
import pytest

from app.core.storage_paths import avatar_path_for, is_safe_object_path, owned_avatar_path
from app.integrations.storage_provider import StorageError, SupabaseStorageProvider

OWNER = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")
FILE_ID = "a" * 32


def test_own_avatar_path_is_accepted() -> None:
    path = avatar_path_for(OWNER, FILE_ID)
    assert owned_avatar_path(OWNER, path) == path


@pytest.mark.parametrize(
    "path",
    [
        f"{OTHER}/{FILE_ID}.webp",  # another user's folder
        f"../message-attachments/{OTHER}/{FILE_ID}.pdf",  # leaves the bucket
        f"{OWNER}/../{OTHER}/{FILE_ID}.webp",
        f"{OWNER}/{FILE_ID}.png",
        f"{OWNER}/{FILE_ID}.webp/extra",
        f"/{OWNER}/{FILE_ID}.webp",
        f"{OWNER}/short.webp",
        "",
        None,
    ],
)
def test_foreign_or_malformed_avatar_path_is_ignored(path: str | None) -> None:
    assert owned_avatar_path(OWNER, path) is None


@pytest.mark.parametrize(
    ("path", "safe"),
    [
        (f"{OWNER}/{FILE_ID}.webp", True),
        ("../other-bucket/x", False),
        ("a/./b", False),
        ("a//b", False),
        ("/a/b", False),
        ("a\\b", False),
        ("", False),
    ],
)
def test_object_path_rules(path: str, safe: bool) -> None:
    assert is_safe_object_path(path) is safe


async def test_provider_never_calls_storage_for_a_traversal_path() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"signedURL": "/object/sign/x?token=t"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SupabaseStorageProvider(
        base_url="https://example.supabase.test",
        service_role_key="test-key",
        bucket="avatars",
        client=client,
    )
    bad = "../message-attachments/c/f.pdf"
    with pytest.raises(StorageError):
        await provider.signed_url(bad, 60)
    with pytest.raises(StorageError):
        await provider.delete(bad)
    with pytest.raises(StorageError):
        await provider.upload(bad, b"x", "image/webp")
    assert calls == []

    assert await provider.signed_url(avatar_path_for(OWNER, FILE_ID), 60)
    assert len(calls) == 1
    assert "/object/sign/avatars/" in str(calls[0].url)
    await client.aclose()
