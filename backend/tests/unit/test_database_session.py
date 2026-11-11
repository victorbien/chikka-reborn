import pytest

from app.core.exceptions import ServiceUnavailableError
from app.database.session import Database, build_database, session_scope
from app.models import Base


def test_build_database_returns_none_without_url() -> None:
    assert build_database(None) is None


async def test_session_scope_fails_explicitly_without_database() -> None:
    with pytest.raises(ServiceUnavailableError) as raised:
        async for _ in session_scope(None):
            pass
    assert raised.value.details["reason"] == "database_not_configured"


async def test_session_scope_rolls_back_and_reraises_on_error() -> None:
    # The engine connects lazily, so no database is contacted by this test.
    database = Database("postgresql+asyncpg://user:pw@127.0.0.1:1/none")
    scope = session_scope(database)
    session = await anext(scope)
    with pytest.raises(RuntimeError, match="boom"):
        await scope.athrow(RuntimeError("boom"))
    assert not session.in_transaction()
    await database.dispose()


def test_declarative_base_uses_project_naming_convention() -> None:
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
