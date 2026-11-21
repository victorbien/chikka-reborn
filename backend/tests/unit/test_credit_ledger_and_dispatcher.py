"""DB-free checks for the error paths of the credit ledger and the dispatcher lifecycle."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError

from app.core.config import Settings
from app.integrations.email.mock import MockEmailProvider
from app.modules.credits import ledger
from app.modules.credits.ledger import InsufficientCreditsError
from app.modules.credits.service import balance_hint
from app.modules.notifications.dispatcher import NotificationDispatcher
from app.realtime.hub import RealtimeHub


class _Nested:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class FailingSession:
    """An AsyncSession stand-in whose insert fails with the given database message."""

    def __init__(self, message: str) -> None:
        self._message = message

    def begin_nested(self) -> _Nested:
        return _Nested()

    async def execute(self, *_: Any, **__: Any) -> Any:
        raise DBAPIError("insert", {}, Exception(self._message))


async def insert(session: object) -> None:
    await ledger.insert_entry(
        session,  # type: ignore[arg-type]
        user_id=uuid4(),
        ledger="demo",
        entry_type="reservation",
        balance_delta=0,
        reserved_delta=100,
        message_id=uuid4(),
    )


async def test_an_overdraw_becomes_a_402_with_the_amounts() -> None:
    session = FailingSession("INSUFFICIENT_CREDITS: available 40 units, required 100 units")

    with pytest.raises(InsufficientCreditsError) as caught:
        await insert(session)

    assert caught.value.status_code == 402 and caught.value.code == "insufficient_credits"
    assert caught.value.details == {"available_units": 40, "required_units": 100}


async def test_an_overdraw_without_amounts_still_becomes_a_402() -> None:
    with pytest.raises(InsufficientCreditsError) as caught:
        await insert(FailingSession("INSUFFICIENT_CREDITS"))

    assert caught.value.details == {}


async def test_other_database_errors_are_not_disguised_as_a_shortfall() -> None:
    with pytest.raises(DBAPIError):
        await insert(
            FailingSession("LEDGER_MISMATCH: simulated message cannot use the live ledger")
        )


@pytest.mark.parametrize(
    ("available", "cost", "simulated", "sufficient", "low"),
    [
        (5000, 100, True, True, False),
        (50, 100, True, False, True),
        (100, 100, True, True, True),  # exactly enough, and at the threshold
        (5000, None, True, None, False),  # unknown cost
        (0, 100, False, True, False),  # live sends are not metered
    ],
)
def test_balance_hint(
    available: int, cost: int | None, simulated: bool, sufficient: bool | None, low: bool
) -> None:
    hint = balance_hint(
        available_units=available, cost_units=cost, is_simulated=simulated, threshold_units=500
    )

    assert hint.sufficient is sufficient and hint.is_low is (
        low or (simulated and available <= 500)
    )
    assert hint.charges_apply is simulated
    assert hint.ledger == ("demo" if simulated else "live")


# -- dispatcher lifecycle --------------------------------------------------------------------


class _EmptyResult:
    def mappings(self) -> "_EmptyResult":
        return self

    def all(self) -> list[Any]:
        return []


class _EmptySession:
    async def execute(self, *_: Any, **__: Any) -> _EmptyResult:
        return _EmptyResult()


class CountingDatabase:
    def __init__(self, *, fail: bool = False) -> None:
        self.transactions = 0
        self._fail = fail

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[_EmptySession]:
        self.transactions += 1
        if self._fail:
            raise RuntimeError("database down")
        yield _EmptySession()


def dispatcher(database: CountingDatabase) -> NotificationDispatcher:
    return NotificationDispatcher(
        settings=Settings(_env_file=None, app_env="test", notifications_worker_poll_seconds=0.01),  # type: ignore[call-arg]
        database=database,  # type: ignore[arg-type]
        hub=RealtimeHub(),
        email=MockEmailProvider(),
    )


async def test_the_loop_runs_until_stopped_and_stops_cleanly() -> None:
    database = CountingDatabase()
    worker = dispatcher(database)

    worker.start()
    worker.start()  # starting twice keeps one loop
    await asyncio.sleep(0.05)
    await worker.stop()
    seen = database.transactions
    await asyncio.sleep(0.03)

    assert seen >= 2
    assert database.transactions == seen  # nothing runs after stop
    await worker.stop()  # stopping twice is harmless


async def test_the_loop_survives_a_failing_pass(caplog: pytest.LogCaptureFixture) -> None:
    database = CountingDatabase(fail=True)
    worker = dispatcher(database)

    worker.start()
    await asyncio.sleep(0.05)
    await worker.stop()

    assert database.transactions >= 2  # it kept trying after the first failure
    assert "notification dispatch failed" in caplog.text


async def test_an_empty_pass_does_nothing() -> None:
    assert await dispatcher(CountingDatabase()).run_once() == (0, 0)
