import os
from typing import Union

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import inspect

# Create an SQLAlchemy engine
username = 'craig'
password = 'securePassword1'
database_name = 'craig_dev'
engine = create_engine(
    f'postgresql://{username}:{password}@localhost:5432/{database_name}')

Base = declarative_base()


class Song(Base):
    __tablename__ = 'song'

    id = Column(Integer, primary_key=True)
    reference = Column(String)
    title = Column(String, nullable=True)
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
        pass

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
    def get_by_reference(cls, reference: str) -> Union['Song', None]:
        return cls.query.filter_by(reference=reference).one_or_none()

    def pop_from_queue(self, guild: Union['Guild', int]) -> 'Song':
        return self.queues.query.filter_by(guild_id=getattr(guild, 'id', guild)).first().pop()

    def do_commit(self) -> None:
        session = inspect(self).session
        session.commit()


class Queue(Base):
    __tablename__ = 'queue'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guild.id'))
    song_id = Column(Integer, ForeignKey('song.id'))

    guild = relationship("Guild", backref="queues")
    song = relationship("Song", backref="queues")

    def pop(self) -> Song:
        session = inspect(self).session
        session.delete(self)
        return self.song
    
    def do_commit(self) -> None:
        session = inspect(self).session
        session.commit()


class Guild(Base):
    __tablename__ = 'guild'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    channel_id = Column(Integer, nullable=True)
    now_playing_song_id = Column(Integer, nullable=True)

    @property
    def queue(self) -> list[Song]:
        return [q.song for q in self.queues.query.order_by(Song.id.desc()).all()]

    @classmethod
    def ensure_guild(cls, id_: str, name: str) -> 'Guild':
        guild = cls.query.filter_by(id=id_).one_or_none()
        if guild is None:
            session = inspect(cls).session
            guild = Guild(id=id_, name=name)
            session.add(guild)
        return guild

    def add_song_to_queue(self, song: Song) -> None:
        session = inspect(self).session
        queue = Queue(guild_id=self.id, song_id=song.id)
        session.add(queue)
        
    def do_commit(self) -> None:
        session = inspect(self).session
        session.commit()


# Create tables
Base.metadata.create_all(engine)
