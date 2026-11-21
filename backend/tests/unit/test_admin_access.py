"""Role restrictions on every administration endpoint, without a database.

The account lookup is faked, so these tests prove the router dependency refuses anyone the
database does not mark as an administrator, whatever the token claims.
"""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeAccountLookup

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = "00000000-0000-0000-0000-000000000002"

ADMIN_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/v1/admin/dashboard"),
    ("GET", "/api/v1/admin/users"),
    ("GET", f"/api/v1/admin/users/{OTHER_ID}"),
    ("POST", f"/api/v1/admin/users/{OTHER_ID}/restrict"),
    ("POST", f"/api/v1/admin/users/{OTHER_ID}/reinstate"),
    ("GET", "/api/v1/admin/sms/messages"),
    ("GET", f"/api/v1/admin/sms/messages/{OTHER_ID}"),
    ("GET", "/api/v1/admin/providers/overview"),
    ("GET", "/api/v1/admin/ai/metrics"),
    ("GET", "/api/v1/admin/audit-logs"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_anonymous_requests_are_rejected(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_ordinary_users_are_refused(
    client: TestClient, make_token: Callable[..., str], method: str, path: str
) -> None:
    headers = {"Authorization": f"Bearer {make_token(sub=str(USER_ID))}"}
    response = client.request(method, path, headers=headers, json={"reason_code": "spam"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_a_role_claimed_by_the_browser_is_ignored(
    client: TestClient, make_token: Callable[..., str], method: str, path: str
) -> None:
    token = make_token(
        sub=str(USER_ID),
        app_metadata={"role": "admin", "roles": ["admin"]},
        user_metadata={"role": "admin"},
    )
    headers = {"Authorization": f"Bearer {token}", "X-User-Role": "admin"}
    response = client.request(
        method, f"{path}?role=admin", headers=headers, json={"reason_code": "spam"}
    )
    assert response.status_code == 403


def test_a_database_administrator_passes_the_role_check(
    client: TestClient, make_token: Callable[..., str], account_lookup: FakeAccountLookup
) -> None:
    account_lookup.roles[USER_ID] = "admin"
    headers = {"Authorization": f"Bearer {make_token(sub=str(USER_ID))}"}
    response = client.get("/api/v1/admin/dashboard", headers=headers)
    # Past the role check. Without a database the service is unavailable, not forbidden.
    assert response.status_code == 503


def test_unverified_administrators_are_refused(
    client: TestClient, make_token: Callable[..., str], account_lookup: FakeAccountLookup
) -> None:
    account_lookup.roles[USER_ID] = "admin"
    account_lookup.statuses[USER_ID] = "pending_verification"
    headers = {"Authorization": f"Bearer {make_token(sub=str(USER_ID))}"}
    assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 403


def test_suspended_administrators_are_refused(
    client: TestClient, make_token: Callable[..., str], account_lookup: FakeAccountLookup
) -> None:
    account_lookup.roles[USER_ID] = "admin"
    account_lookup.statuses[USER_ID] = "suspended"
    headers = {"Authorization": f"Bearer {make_token(sub=str(USER_ID))}"}
    assert client.get("/api/v1/admin/dashboard", headers=headers).status_code == 403
