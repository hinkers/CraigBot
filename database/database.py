import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

_async_sessionmaker = None
_sync_sessionmaker = None


def with_driver(url: str, async_: bool) -> str:
    """Return the Postgres URL with its scheme set to the asyncpg (async) or psycopg2 (sync) driver."""
    _, rest = url.split('://', 1)
    scheme = 'postgresql+asyncpg' if async_ else 'postgresql'
    return f'{scheme}://{rest}'


def get_database_url(async_=True) -> str:
    url = os.getenv('DATABASE_URL')
    if url is None:
        username = os.getenv('DB_USERNAME')
        password = os.getenv('DB_PASSWORD')
        database_name = os.getenv('DB_DATABASE_NAME')
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        url = f'postgresql://{username}:{password}@{host}:{port}/{database_name}'
    return with_driver(url, async_)


def get_engine(async_=True):
    if os.getenv('craig_debug') == 'true':
        load_dotenv('dev.env')
    else:
        load_dotenv('prod.env')

    # Create an SQLAlchemy engine
    if async_:
        return create_async_engine(
            get_database_url(async_=True),
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20
        )
    return create_engine(
        get_database_url(async_=False),
        pool_pre_ping=True,
        pool_recycle=3600
    )


def get_sessionmaker():
    """Shared async session factory; the engine is created on first use, not at import."""
    global _async_sessionmaker
    if _async_sessionmaker is None:
        _async_sessionmaker = async_sessionmaker(
            autocommit=False, autoflush=False, expire_on_commit=False, bind=get_engine(), class_=AsyncSession
        )
    return _async_sessionmaker


def get_sync_sessionmaker():
    """Shared sync session factory for Celery tasks; the engine is created on first use."""
    global _sync_sessionmaker
    if _sync_sessionmaker is None:
        _sync_sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=get_engine(async_=False))
    return _sync_sessionmaker
