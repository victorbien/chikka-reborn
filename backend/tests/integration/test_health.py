from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.deps import get_optional_db_session


class FakeSession:
    """Stands in for AsyncSession; no real database is used in tests."""

    def __init__(self, *, fail: bool) -> None:
        self._fail = fail

    async def execute(self, *_args: Any, **_kwargs: Any) -> None:
        if self._fail:
            raise OperationalError("select 1", {}, Exception("connection refused"))


def use_session(app: FastAPI, session: FakeSession) -> None:
    async def override() -> AsyncIterator[FakeSession]:
        yield session

    app.dependency_overrides[get_optional_db_session] = override


def test_health_responds_without_database(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "chikka-reborn-api"
    assert body["environment"] == "test"
    assert body["sms_mode"] == "simulation"
    assert body["database"] == "not_configured"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_health_reports_database_ok(app: FastAPI, client: TestClient) -> None:
    use_session(app, FakeSession(fail=False))
    body = client.get("/api/v1/health").json()
    assert body["database"] == "ok"
    assert body["status"] == "ok"


def test_health_degrades_but_stays_live_when_database_is_down(
    app: FastAPI, client: TestClient
) -> None:
    use_session(app, FakeSession(fail=True))
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unavailable"


def test_readiness_is_503_when_database_is_down(app: FastAPI, client: TestClient) -> None:
    use_session(app, FakeSession(fail=True))
    assert client.get("/api/v1/health/ready").status_code == 503


def test_readiness_is_200_when_nothing_is_down(client: TestClient) -> None:
    assert client.get("/api/v1/health/ready").status_code == 200


def test_platform_aliases_match_versioned_routes(app: FastAPI, client: TestClient) -> None:
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").status_code == 200
    use_session(app, FakeSession(fail=True))
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503


def test_caller_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "caller-id-12345"})
    assert response.headers["X-Request-ID"] == "caller-id-12345"
    assert response.json()["request_id"] == "caller-id-12345"


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
