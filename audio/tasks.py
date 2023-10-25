import os
from audio.database import Song

import converter
from ytdl_source import YTDLSource
from celery import Celery

app = Celery(
    'main',
    broker=f"redis://localhost:6379/{1 if os.getenv('craig_debug') == 'true' else 0}"
)


@app.task
def equalise_loudness(song: Song):
    converter.equalise_loudness(song)


@app.task
def download(song: Song):
    YTDLSource.download(song)

    # TODO: Check if able to normalize

    song.do_commit()
