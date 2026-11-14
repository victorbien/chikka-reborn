"""End-to-end API flows against a real PostgreSQL schema.

* Database: supabase/tools/serve-db.mjs (PGlite with every migration and the Supabase stub).
* Supabase Auth and Storage: tests/support/fake_supabase.py over an in-process ASGI transport,
  called through the real SupabaseAuthProvider / SupabaseStorageProvider.
* SMS: SimulatedOtpDelivery. Nothing leaves the machine.

Skipped (not failed) when Node.js or the database tools are not installed.
"""

import asyncio
import queue
import random
import shutil
import socket
import subprocess
import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.container import Providers
from app.core.config import Settings
from app.integrations.auth_provider import SupabaseAuthProvider
from app.integrations.otp_delivery import SimulatedInbox, SimulatedOtpDelivery
from app.integrations.sms.base import SmsProvider
from app.integrations.sms.mock import MockSmsProvider
from app.integrations.storage_provider import SupabaseStorageProvider
from app.main import create_app
from app.modules.sms.gateway import SmsGateway
from tests.conftest import TEST_JWT_SECRET
from tests.support.fake_supabase import FakeSupabase

TOOLS_DIR = Path(__file__).resolve().parents[3] / "supabase" / "tools"
FAKE_BASE = "http://fake-supabase.test"
ANON_KEY = "test-anon-key"
SERVICE_KEY = "test-service-role-key"
PASSWORD = "Correct-Horse-7"
MOCK_WEBHOOK_SECRET = "test-only-mock-webhook-secret"


class FakeClock:
    """Shared by the SMS provider, engine and service so retries and timelines are exact."""

    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _free_port_pair() -> int:
    for _ in range(50):
        with socket.socket() as first:
            first.bind(("127.0.0.1", 0))
            port = int(first.getsockname()[1])
        with socket.socket() as second:
            try:
                second.bind(("127.0.0.1", port + 1))
            except OSError:
                continue
        return port
    raise RuntimeError("no free port pair")


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    node = shutil.which("node")
    if (
        node is None
        or not (TOOLS_DIR / "node_modules" / "@electric-sql" / "pglite-socket").exists()
    ):
        pytest.skip("Node.js and supabase/tools dependencies (npm ci) are required for flow tests")
    port = _free_port_pair()
    process = subprocess.Popen(  # noqa: S603 - fixed arguments
        [node, "serve-db.mjs", f"--port={port}"],
        cwd=TOOLS_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    lines: queue.Queue[str] = queue.Queue()

    def pump() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line)

    threading.Thread(target=pump, daemon=True).start()
    url: str | None = None
    output: list[str] = []
    try:
        while url is None:
            line = lines.get(timeout=120)
            output.append(line)
            if line.startswith("READY "):
                url = line.split(" ", 1)[1].strip()
    except queue.Empty:
        process.kill()
        pytest.fail("database server did not start:\n" + "".join(output))
    try:
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


async def _sql(url: str, statement: str, *args: Any) -> list[asyncpg.Record]:
    connection = await asyncpg.connect(url, statement_cache_size=0)
    try:
        return list(await connection.fetch(statement, *args))
    finally:
        await connection.close()


@dataclass
class Harness:
    client: TestClient
    fake: FakeSupabase
    inbox: SimulatedInbox
    settings: Settings
    database_url: str
    clock: FakeClock
    sms: MockSmsProvider
    gateway: SmsGateway

    def run_worker(self) -> int:
        """One deterministic pass of the SMS worker (the background loop is off in tests)."""
        return int(self.client.portal.call(self.gateway.worker.run_once))  # type: ignore[union-attr]

    # -- database access for assertions ------------------------------------------------

    def sql(self, statement: str, *args: Any) -> list[asyncpg.Record]:
        return asyncio.run(_sql(self.database_url, statement, *args))

    def profile(self, user_id: str) -> asyncpg.Record:
        rows = self.sql("select * from public.profiles where id = $1", uuid.UUID(user_id))
        assert rows, "profile missing"
        return rows[0]

    # -- common flows ------------------------------------------------------------------

    @staticmethod
    def email() -> str:
        return f"user-{uuid.uuid4().hex[:12]}@example.com"

    def register(
        self, email: str, password: str = PASSWORD, name: str = "Marites Santos"
    ) -> httpx.Response:
        return self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "display_name": name, "accept_terms": True},
        )

    def verify(self, email: str) -> httpx.Response:
        token_hash = self.fake.last_email(email, "signup").token_hash
        return self.client.post("/api/v1/auth/verify-email", json={"token_hash": token_hash})

    def login(self, email: str, password: str = PASSWORD) -> httpx.Response:
        return self.client.post("/api/v1/auth/login", json={"email": email, "password": password})

    def signed_up_user(self, email: str | None = None) -> tuple[str, dict[str, str]]:
        """Register, verify and sign in. Returns (email, auth headers)."""
        email = email or self.email()
        assert self.register(email).status_code == 202
        assert self.verify(email).status_code == 200
        response = self.login(email)
        assert response.status_code == 200, response.text
        return email, {"Authorization": f"Bearer {response.json()['data']['access_token']}"}

    def onboarded_user(self) -> tuple[str, dict[str, str]]:
        email, headers = self.signed_up_user()
        response = self.client.post(
            "/api/v1/users/me/onboarding",
            json={"username": f"u_{uuid.uuid4().hex[:10]}", "display_name": "Marites Santos"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        return email, headers

    def user_id(self, headers: dict[str, str]) -> str:
        return str(self.client.get("/api/v1/users/me", headers=headers).json()["data"]["id"])


def reset_sms_state(database_url: str) -> None:
    """Shared fixtures start clean: counters, reply routes, opt-outs, the active provider."""
    # Rate-limit counters are shared by every test client (same address); start clean.
    asyncio.run(_sql(database_url, "delete from public.rate_limit_counters"))
    # Reply routes and opt-outs are keyed by shared fictional numbers.
    asyncio.run(
        _sql(
            database_url,
            "update public.sms_routes set status = 'released', released_at = now(), "
            "release_reason = 'test' where status = 'active'",
        )
    )
    asyncio.run(_sql(database_url, "delete from public.sms_opt_outs"))
    # Provider rows are shared across tests: the simulation is the default.
    asyncio.run(_sql(database_url, "update public.provider_configurations set is_active = false"))
    asyncio.run(
        _sql(
            database_url,
            "update public.provider_configurations set is_active = true where provider = 'mock'",
        )
    )


def build_harness(
    database_url: str,
    *,
    provider_factory: Callable[[FakeClock], SmsProvider] | None = None,
    settings_extra: dict[str, Any] | None = None,
) -> Iterator[Harness]:
    reset_sms_state(database_url)
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=database_url,
        db_pool_size=4,
        db_max_overflow=0,
        supabase_url=FAKE_BASE,
        supabase_anon_key=ANON_KEY,  # type: ignore[arg-type]
        supabase_service_role_key=SERVICE_KEY,  # type: ignore[arg-type]
        supabase_jwt_secret=TEST_JWT_SECRET,  # type: ignore[arg-type]
        app_secret_key="test-only-app-secret-key-0123456789",  # type: ignore[arg-type]
        sms_mock_webhook_secret=MOCK_WEBHOOK_SECRET,  # type: ignore[arg-type]
        sms_worker_enabled=False,
        # Tests drive the notification dispatcher explicitly (run_once), like the SMS worker.
        notifications_worker_enabled=False,
        **{"sms_public_base_url": "https://api.example.test", **(settings_extra or {})},
    )
    clock = FakeClock()
    sms: SmsProvider = (
        provider_factory(clock)
        if provider_factory
        else MockSmsProvider(secret=MOCK_WEBHOOK_SECRET, clock=clock)
    )
    fake = FakeSupabase(
        database_url=settings.database_url or "",
        jwt_secret=TEST_JWT_SECRET,
        anon_key=ANON_KEY,
        service_role_key=SERVICE_KEY,
    )
    transport = httpx.ASGITransport(app=fake.app)
    inbox = SimulatedInbox()
    providers = Providers(
        auth=SupabaseAuthProvider(
            base_url=FAKE_BASE,
            anon_key=ANON_KEY,
            service_role_key=SERVICE_KEY,
            client=httpx.AsyncClient(transport=transport),
        ),
        storage=SupabaseStorageProvider(
            base_url=FAKE_BASE,
            service_role_key=SERVICE_KEY,
            bucket="avatars",
            client=httpx.AsyncClient(transport=transport),
        ),
        otp=SimulatedOtpDelivery(inbox),
        inbox=inbox,
        attachment_storage=SupabaseStorageProvider(
            base_url=FAKE_BASE,
            service_role_key=SERVICE_KEY,
            bucket="message-attachments",
            client=httpx.AsyncClient(transport=transport),
        ),
        sms=sms,
        clock=clock,
        rng=random.Random(1234),
    )
    app = create_app(settings, providers=providers)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Harness(
            client=client,
            fake=fake,
            inbox=inbox,
            settings=settings,
            database_url=database_url,
            clock=clock,
            sms=sms,  # type: ignore[arg-type]
            gateway=app.state.sms_gateway,
        )
        client.portal.call(providers.aclose)  # type: ignore[union-attr]
        client.portal.call(fake.aclose)  # type: ignore[union-attr]


@pytest.fixture
def harness(database_url: str) -> Iterator[Harness]:
    yield from build_harness(database_url)
