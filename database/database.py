
from sqlalchemy import (create_engine)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base


# Create an SQLAlchemy engine
username = 'craig'
password = 'securePassword1'
database_name = 'craig_dev'

Base = declarative_base()


def get_engine(async_=True):
    if async_:
        return create_async_engine(
            f'postgresql+asyncpg://{username}:{password}@localhost:5432/{database_name}')
    return create_engine(
        f'postgresql://{username}:{password}@localhost:5432/{database_name}')

