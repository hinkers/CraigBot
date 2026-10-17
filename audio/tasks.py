import os
from datetime import datetime

from celery import Celery
from dotenv import load_dotenv

import audio.converter as converter
from audio.ytdl_source import YTDLSource
from database.audio import Song
from database.database import get_sync_sessionmaker

debug = False
if os.getenv('craig_debug') == 'true':
    debug = True

load_dotenv('dev.env' if debug else 'prod.env')

broker_id = 0
backend_id = 1
if debug:
    broker_id = 2
    backend_id = 3

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

app = Celery(
    'audio.tasks',
    broker=f"{redis_url}/{broker_id}",
    backend=f"{redis_url}/{backend_id}"
)


@app.task
def equalise_loudness(song_id: int, swap_now=True):
    return
    with get_sync_sessionmaker()() as session:
        song = session.get(Song, song_id)
        converter.equalise_loudness(song, swap_now)
        song.is_normalized = swap_now
        session.commit()


@app.task
def download(song_id: int):
    with get_sync_sessionmaker()() as session:
        song = session.get(Song, song_id)
        song.is_downloaded = YTDLSource.download(song)

        if song.is_downloaded:
            song.date_downloaded = datetime.now()

        song.has_download_task = False
        session.commit()
