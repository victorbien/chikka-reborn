"""Wiring and the background worker for the SMS engine.

The worker is an in-process asyncio loop (ADL: modular monolith, no broker). It is safe to run
in several instances: dispatch claims rows with FOR UPDATE SKIP LOCKED and a lease. Tests turn
the loop off and call run_once() so time and ordering stay deterministic.
"""

import asyncio
import contextlib
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.config import Settings
from app.database.session import Database
from app.integrations.sms.base import SmsProvider
from app.modules.audit.service import AuditLogger
from app.modules.rate_limits.service import RateLimiter
from app.modules.sms.engine import SmsEngine
from app.modules.sms.repository import SmsRepository
from app.modules.sms.webhooks import WebhookService
from app.realtime.hub import RealtimeHub

logger = logging.getLogger(__name__)

MAX_PASSES = 5


class SmsWorker:
    def __init__(
        self,
        *,
        engine: SmsEngine,
        webhooks: WebhookService,
        provider: SmsProvider,
        poll_seconds: float,
    ) -> None:
        self._engine = engine
        self._webhooks = webhooks
        self._provider = provider
        self._poll_seconds = poll_seconds
        self._wakeup = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def wake(self) -> None:
        """Called after a message is queued so dispatch does not wait for the next poll."""
        self._wakeup.set()

    async def run_once(self) -> int:
        """Do all the work that is due now. Returns how many items were handled."""
        total = 0
        for _ in range(MAX_PASSES):
            handled = 0
            # Simulated callbacks go through the same signed webhook path as live ones.
            for callback in await self._provider.pending_callbacks():
                try:
                    await self._webhooks.deliver_simulated(callback)
                except Exception:
                    logger.exception("simulated callback failed")
                handled += 1
            handled += await self._engine.dispatch_due()
            handled += await self._webhooks.process_pending()
            handled += await self._engine.reconcile()
            total += handled
            if handled == 0:
                break
        return total

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("sms worker pass failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wakeup.wait(), timeout=self._poll_seconds)
            self._wakeup.clear()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="sms-worker")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None


@dataclass
class SmsGateway:
    provider: SmsProvider
    engine: SmsEngine
    webhooks: WebhookService
    worker: SmsWorker
    limiter: RateLimiter


def build_gateway(
    *,
    settings: Settings,
    database: Database,
    provider: SmsProvider,
    hub: RealtimeHub,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    rng: random.Random | None = None,
) -> SmsGateway:
    audit = AuditLogger(database)
    limiter = RateLimiter(database, settings)
    engine = SmsEngine(
        settings=settings,
        database=database,
        provider=provider,
        audit=audit,
        hub=hub,
        clock=clock,
        rng=rng,
    )
    webhooks = WebhookService(
        settings=settings,
        database=database,
        provider=provider,
        engine=engine,
        limiter=limiter,
        audit=audit,
        clock=clock,
    )
    worker = SmsWorker(
        engine=engine,
        webhooks=webhooks,
        provider=provider,
        poll_seconds=settings.sms_worker_poll_seconds,
    )
    return SmsGateway(provider, engine, webhooks, worker, limiter)


async def announce_mode(database: Database, provider: SmsProvider) -> None:
    """Startup: make the database agree with the configured mode, and record it.

    Simulation is safe to enforce (it can never send anything). Live is never switched on
    here: an administrator confirms it per environment, and until then sends fail loudly.
    """
    audit = AuditLogger(database)
    async with database.transaction() as session:
        if provider.name == "mock":
            await session.execute(
                text(
                    "update public.provider_configurations set is_active = false "
                    "where is_active and provider <> 'mock'"
                )
            )
            await session.execute(
                text(
                    "update public.provider_configurations set is_active = true "
                    "where provider = 'mock' and mode = 'simulation'"
                )
            )
        active = await SmsRepository(session).active_provider()
    if active is None or active.provider != provider.name:
        logger.error(
            "sms provider configuration does not match the running mode: sends will be refused",
            extra={"configured": provider.name},
        )
    await audit.record_standalone(
        category="sms",
        action="sms.mode_started",
        metadata={
            "provider": provider.name,
            "mode": provider.mode,
            "database_active": active.provider if active else "none",
        },
    )
