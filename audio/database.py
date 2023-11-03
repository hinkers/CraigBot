import os
from typing import Union

from sqlalchemy import (BigInteger, Boolean, Column, Date, DateTime,
                        ForeignKey, Integer, String, create_engine, event,
                        inspect, select)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

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


class Song(Base):
    __tablename__ = 'audio.songs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference = Column(String)
    title = Column(String, nullable=True)
    channel = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    view_count = Column(Integer, nullable=True)
    like_count = Column(Integer, nullable=True)
    filename = Column(String, nullable=True)
    extension = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    is_normalized = Column(Boolean, default=False)
    is_downloaded = Column(Boolean, default=False)
    date_downloaded = Column(Date, nullable=True)
    date_last_played = Column(Date, nullable=True)

    @property
    def info(self) -> dict[str, str]:
        return dict(
            title=self.title,
            webpage_url=self.link,
            thumbnail=self.thumbnail,
            channel=self.channel,
            duration_string=str(self.duration),
            duration=self.duration,
            view_count=self.view_count,
            like_count=self.like_count
        )

    @property
    def full_filename(self) -> str:
        return os.path.join('data', 'audio_cache', f'{self.filename}.{self.extension}')

    @property
    def full_filename_without_extension(self) -> str:
        return os.path.join('data', 'audio_cache', self.filename)

    @property
    def link(self) -> str:
        return f'https://www.youtube.com/watch?v={self.reference}'

    @classmethod
    async def get_by_reference(cls, session, reference: str) -> Union['Song', None]:
        statement = select(cls).where(cls.reference == reference)
        result = await session.execute(statement)
        return result.scalar()

    def __str__(self):
        if self.title is None:
            return self.link
        return f'[{self.title}] {self.link}'


class Queue(Base):
    __tablename__ = 'audio.queues'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, ForeignKey('guild.id'))
    song_id = Column(Integer, ForeignKey('song.id'))
    order_id = Column(Integer)

    guild = relationship("Guild", backref="queues")
    song = relationship("Song", backref="queues")


@event.listens_for(Queue, 'before_insert')
def before_insert(mapper, connection, target):
    target.order_id = connection.scalar(
        select([func.count(Queue.id)]).where(Queue.guild_id == target.guild_id)
    ) + 1


class Guild(Base):
    __tablename__ = 'audio.guilds'

    id = Column(BigInteger, primary_key=True)
    name = Column(String)
    channel_id = Column(Integer, nullable=True)
    now_playing_song_id = Column(Integer, ForeignKey('song.id'), nullable=True)
    now_playing_started = Column(DateTime, nullable=True)

    song = relationship("Song", backref="now_playing_guilds")

    @property
    def is_playing(self):
        return True if self.now_playing_song_id is not None else False

    @classmethod
    async def ensure_guild(cls, session, id_: str, name: str) -> 'Guild':
        guild = await session.get(cls, id_)
        if guild is None:
            guild = Guild(id=id_, name=name)
            session.add(guild)
        return guild

    def add_song_to_queue(self, song: Song) -> None:
        session = inspect(self).session
        queue = Queue(guild_id=self.id, song_id=song.id)
        session.add(queue)


class Favourite(Base):
    __tablename__ = 'audio.favourites'

    id = Column(BigInteger, primary_key=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String)
    song_id = Column(Integer, nullable=False)

    song = relationship("Song", backref="favourites")


if __name__ == '__main__':
    with get_engine(async_=False).begin():
        Base.metadata.create_all()
