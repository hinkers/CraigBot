import os
from datetime import datetime

from celery import Celery
from sqlalchemy.orm import sessionmaker

import audio.converter as converter
from audio.ytdl_source import YTDLSource
from database.audio import Song
from database.database import get_engine

debug = False
if os.getenv('craig_debug') == 'true':
    debug = True

Session = sessionmaker(autocommit=False, autoflush=False, bind=get_engine(async_=False))

broker_id = 0
backend_id = 1
if debug:
    broker_id = 2
    backend_id = 3

app = Celery(
    'audio.tasks',
    broker=f"redis://localhost:6379/{broker_id}",
    backend=f"redis://localhost:6379/{backend_id}"
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
