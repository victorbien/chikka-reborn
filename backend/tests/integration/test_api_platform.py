from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.deps import AdminUserDep, CurrentUserDep
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.main import create_app
from tests.conftest import FakeAccountLookup

USER_1 = "00000000-0000-0000-0000-000000000001"


class Payload(BaseModel):
    phone: str


def add_test_routes(app: FastAPI) -> None:
    @app.get("/test/me")
    async def me(user: CurrentUserDep) -> dict[str, str]:
        return {"id": str(user.id), "role": user.role}

    @app.get("/test/admin")
    async def admin(user: AdminUserDep) -> dict[str, str]:
        return {"id": str(user.id)}

    @app.get("/test/missing")
    async def missing() -> None:
        raise NotFoundError("Nothing here.")

    @app.get("/test/boom")
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    @app.post("/test/validate")
    async def validate(payload: Payload) -> Payload:
        return payload


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_domain_error_is_mapped_to_envelope(app: FastAPI, client: TestClient) -> None:
    add_test_routes(app)
    response = client.get("/test/missing")
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "Nothing here.",
        "details": {},
    }


def test_unhandled_error_does_not_leak_internals(app: FastAPI, client: TestClient) -> None:
    add_test_routes(app)
    response = client.get("/test/boom")
    assert response.status_code == 500
    assert "hunter2" not in response.text
    assert response.json()["error"]["code"] == "internal_error"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_validation_error_does_not_echo_submitted_values(app: FastAPI, client: TestClient) -> None:
    add_test_routes(app)
    response = client.post("/test/validate", json={"phone": 12345, "extra": "private-value"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "private-value" not in response.text
    assert response.json()["error"]["details"]["problems"][0]["field"] == "body.phone"


def test_protected_route_without_token_is_401(app: FastAPI, client: TestClient) -> None:
    add_test_routes(app)
    response = client.get("/test/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_protected_route_with_bad_token_is_401(app: FastAPI, client: TestClient) -> None:
    add_test_routes(app)
    response = client.get("/test/me", headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401


def test_protected_route_with_valid_token(
    app: FastAPI, client: TestClient, make_token: Callable[..., str]
) -> None:
    add_test_routes(app)
    token = make_token(sub=USER_1)
    response = client.get("/test/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"id": USER_1, "role": "user"}


def test_admin_route_denies_regular_user(
    app: FastAPI, client: TestClient, make_token: Callable[..., str]
) -> None:
    add_test_routes(app)
    response = client.get("/test/admin", headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_admin_role_in_token_metadata_is_ignored(
    app: FastAPI, client: TestClient, make_token: Callable[..., str]
) -> None:
    add_test_routes(app)
    token = make_token(app_metadata={"role": "admin"}, user_metadata={"role": "admin"})
    response = client.get("/test/admin", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_route_allows_admin(
    app: FastAPI,
    client: TestClient,
    make_token: Callable[..., str],
    account_lookup: FakeAccountLookup,
) -> None:
    add_test_routes(app)
    import uuid

    account_lookup.roles[uuid.UUID(USER_1)] = "admin"
    token = make_token(sub=USER_1)
    response = client.get("/test/admin", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_auth_fails_closed_when_secret_is_not_configured() -> None:
    unconfigured = create_app(Settings(_env_file=None, app_env="test"))  # type: ignore[call-arg]
    add_test_routes(unconfigured)
    with TestClient(unconfigured, raise_server_exceptions=False) as test_client:
        response = test_client.get("/test/me", headers={"Authorization": "Bearer anything"})
    assert response.status_code == 503


def test_revoked_session_is_rejected(
    app: FastAPI,
    client: TestClient,
    make_token: Callable[..., str],
    account_lookup: FakeAccountLookup,
) -> None:
    import uuid

    add_test_routes(app)
    account_lookup.revoked_sessions.add(uuid.UUID("00000000-0000-0000-0000-0000000000aa"))
    response = client.get("/test/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_revoked"


def test_cors_allows_configured_origin(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


def test_cors_blocks_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_allows_idempotency_key(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Idempotency-Key",
        },
    )
    assert response.status_code == 200
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()


def test_api_documentation_is_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    schema = client.get("/api/v1/openapi.json")
    assert schema.status_code == 200
    assert "/api/v1/health" in schema.json()["paths"]


def test_api_documentation_is_off_in_production() -> None:
    production = create_app(
        Settings(_env_file=None, app_env="production", app_secret_key="k" * 32)  # type: ignore[call-arg, arg-type]
    )
    with TestClient(production) as test_client:
        assert test_client.get("/docs").status_code == 404
        assert test_client.get("/api/v1/openapi.json").status_code == 404
