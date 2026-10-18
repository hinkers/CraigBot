import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import database.audio  # noqa: F401  (registers the audio models on Base.metadata)
import database.tag  # noqa: F401  (registers the tag model on Base.metadata)
from database.database import Base, with_driver
from tests.helpers import FakeBot, assert_safe_test_database

LOCAL_TEST_DATABASE_URL = 'postgresql://craig_test:craig_test@localhost:5433/craig_test'


def _test_database_url() -> str:
    return os.getenv('DATABASE_URL', LOCAL_TEST_DATABASE_URL)


@pytest.fixture(scope='session')
def database_schema():
    """Create a fresh schema once per run. Locally, skip DB tests if Postgres is down; in CI, fail."""
    url = _test_database_url()
    assert_safe_test_database(url)
    engine = create_engine(with_driver(url, async_=False), poolclass=NullPool)
    try:
        with engine.begin() as connection:
            Base.metadata.drop_all(connection)
            Base.metadata.create_all(connection)
    except OperationalError as error:
        message = (
            f'Postgres not reachable at {url} ({error.orig}). '
            'Start it with: docker compose -f docker-compose.test.yml up -d --wait'
        )
        if os.getenv('CI'):
            pytest.fail(message)
        pytest.skip(message)
    finally:
        engine.dispose()


@pytest.fixture
async def db_connection(database_schema):
    """An async connection inside a transaction that is rolled back after each test."""
    engine = create_async_engine(with_driver(_test_database_url(), async_=True), poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def session_factory(db_connection):
    """Builds sessions configured like the bot's, whose commits only release a savepoint."""
    def factory():
        return AsyncSession(
            bind=db_connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode='create_savepoint',
        )
    return factory


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


@pytest.fixture
def db_bot(session_factory):
    return FakeBot(session_factory)
