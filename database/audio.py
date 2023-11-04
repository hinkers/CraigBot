import os
from typing import Union

from sqlalchemy import (BigInteger, Boolean, Column, Date, DateTime,
                        ForeignKey, Integer, String, select)
from sqlalchemy.orm import relationship

from database.database import Base, get_engine


class Song(Base):
    __tablename__ = 'audio_song'

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
        return f'[{self.title}]\n{self.link}'


class Queue(Base):
    __tablename__ = 'audio_queue'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, ForeignKey('audio_guild.id'))
    song_id = Column(Integer, ForeignKey('audio_song.id'))
    order_id = Column(Integer, nullable=False)

    guild = relationship("Guild", backref="queues")
    song = relationship("Song", backref="queues")


class Guild(Base):
    __tablename__ = 'audio_guild'

    id = Column(BigInteger, primary_key=True)
    name = Column(String)
    channel_id = Column(Integer, nullable=True)
    now_playing_song_id = Column(Integer, ForeignKey('audio_song.id'), nullable=True)
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

    def add_song_to_queue(self, session, song: Song) -> Queue:
        queue = Queue(guild_id=self.id, song_id=song.id)
        session.add(queue)
        return queue


class Favourite(Base):
    __tablename__ = 'audio_favourite'

    id = Column(BigInteger, primary_key=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String)
    song_id = Column(Integer, ForeignKey('audio_song.id'), nullable=False)

    song = relationship("Song", backref="favourites")


if __name__ == '__main__':
    with get_engine(async_=False).begin() as engine:
        Base.metadata.create_all(bind=engine)
