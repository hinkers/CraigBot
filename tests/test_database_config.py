from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

import database.database as db


def test_with_driver_sets_asyncpg_scheme():
    assert db.with_driver('postgresql://u:p@h:1/d', async_=True) == 'postgresql+asyncpg://u:p@h:1/d'


def test_with_driver_sets_sync_scheme():
    assert db.with_driver('postgresql+asyncpg://u:p@h:1/d', async_=False) == 'postgresql://u:p@h:1/d'


def test_database_url_prefers_database_url(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@h:1/d')

    assert db.get_database_url(async_=True) == 'postgresql+asyncpg://u:p@h:1/d'


def _set_db_credentials(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('DB_HOST', raising=False)
    monkeypatch.delenv('DB_PORT', raising=False)
    monkeypatch.setenv('DB_USERNAME', 'craig')
    monkeypatch.setenv('DB_PASSWORD', 'secret')
    monkeypatch.setenv('DB_DATABASE_NAME', 'craigdb')


def test_database_url_defaults_to_localhost(monkeypatch):
    _set_db_credentials(monkeypatch)

    assert db.get_database_url(async_=False) == 'postgresql://craig:secret@localhost:5432/craigdb'


def test_database_url_uses_host_and_port(monkeypatch):
    _set_db_credentials(monkeypatch)
    monkeypatch.setenv('DB_HOST', 'db.internal')
    monkeypatch.setenv('DB_PORT', '6543')

    assert db.get_database_url(async_=True) == 'postgresql+asyncpg://craig:secret@db.internal:6543/craigdb'


def test_sessionmaker_creates_engine_once(monkeypatch):
    calls = []

    def fake_get_engine(async_=True):
        calls.append(async_)
        return create_async_engine('postgresql+asyncpg://u:p@localhost:1/d')

    monkeypatch.setattr(db, 'get_engine', fake_get_engine)
    monkeypatch.setattr(db, '_async_sessionmaker', None)

    first = db.get_sessionmaker()
    second = db.get_sessionmaker()

    assert first is second
    assert calls == [True]


def test_sync_sessionmaker_creates_engine_once(monkeypatch):
    calls = []

    def fake_get_engine(async_=True):
        calls.append(async_)
        return create_engine('postgresql://u:p@localhost:1/d')

    monkeypatch.setattr(db, 'get_engine', fake_get_engine)
    monkeypatch.setattr(db, '_sync_sessionmaker', None)

    first = db.get_sync_sessionmaker()
    second = db.get_sync_sessionmaker()

    assert first is second
    assert calls == [False]
