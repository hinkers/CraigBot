from datetime import datetime

from celery import Celery
from sqlalchemy.orm import sessionmaker

import audio.converter as converter
from audio.database import Song, get_engine
from audio.ytdl_source import YTDLSource

Session = sessionmaker(autocommit=False, autoflush=False, bind=get_engine(async_=False))

app = Celery(
    'audio.tasks',
    broker=f"redis://localhost:6379/0",
    backend=f"redis://localhost:6379/1"
)


@app.task
def equalise_loudness(song_id: int):
    with Session() as session:
        song = session.get(Song, song_id)
        converter.equalise_loudness(song)
        song.is_normalized = True
        session.commit()


@app.task
def download(song_id: int):
    with Session() as session:
        song = session.get(Song, song_id)
        YTDLSource.download(song)
        song.is_downloaded = True
        song.date_downloaded = datetime.now()

        # TODO: Check if able to normalize

        session.commit()
