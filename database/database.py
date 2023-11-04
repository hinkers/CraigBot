import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def get_engine(async_=True):
    if os.getenv('craig_debug') == 'true':
        load_dotenv('dev.env')
    else:
        load_dotenv('prod.env')

    # Create an SQLAlchemy engine
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')
    database_name = os.getenv('DB_DATABASE_NAME')

    if async_:
        return create_async_engine(
            f'postgresql+asyncpg://{username}:{password}@localhost:5432/{database_name}')
    return create_engine(
        f'postgresql://{username}:{password}@localhost:5432/{database_name}')
