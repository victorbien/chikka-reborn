"""Object storage interface and its Supabase Storage implementation (profile photos)."""

import logging
from typing import Protocol
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Storage unavailable or misconfigured. Callers keep the previous object."""


class StorageProvider(Protocol):
    async def upload(self, path: str, data: bytes, content_type: str) -> None: ...

    async def delete(self, path: str) -> None: ...

    async def signed_url(self, path: str, expires_in: int) -> str: ...


class UnconfiguredStorageProvider:
    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        raise StorageError("Storage is not configured")

    async def delete(self, path: str) -> None:
        raise StorageError("Storage is not configured")

    async def signed_url(self, path: str, expires_in: int) -> str:
        raise StorageError("Storage is not configured")


class SupabaseStorageProvider:
    def __init__(
        self,
        *,
        base_url: str,
        service_role_key: str,
        bucket: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/") + "/storage/v1"
        self._bucket = bucket
        self._headers = {"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}"}
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    def _object_url(self, path: str) -> str:
        return f"{self._base}/object/{self._bucket}/{quote(path)}"

    async def _send(
        self, method: str, url: str, json: dict[str, object] | None = None
    ) -> httpx.Response:
        try:
            response = await self._client.request(method, url, headers=self._headers, json=json)
        except httpx.HTTPError as exc:
            logger.warning("storage unreachable", extra={"error_type": type(exc).__name__})
            raise StorageError("Storage unreachable") from exc
        if response.status_code >= 400:
            logger.warning("storage error", extra={"status_code": response.status_code})
            raise StorageError("Storage request failed")
        return response

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        try:
            response = await self._client.post(
                self._object_url(path),
                content=data,
                headers={**self._headers, "Content-Type": content_type, "x-upsert": "true"},
            )
        except httpx.HTTPError as exc:
            logger.warning("storage unreachable", extra={"error_type": type(exc).__name__})
            raise StorageError("Storage unreachable") from exc
        if response.status_code >= 400:
            logger.warning("storage upload failed", extra={"status_code": response.status_code})
            raise StorageError("Storage upload failed")

    async def delete(self, path: str) -> None:
        await self._send("DELETE", self._object_url(path))

    async def signed_url(self, path: str, expires_in: int) -> str:
        response = await self._send(
            "POST",
            f"{self._base}/object/sign/{self._bucket}/{quote(path)}",
            json={"expiresIn": expires_in},
        )
        signed = response.json().get("signedURL")
        if not isinstance(signed, str):
            raise StorageError("Unexpected storage response")
        return f"{self._base}{signed}"
