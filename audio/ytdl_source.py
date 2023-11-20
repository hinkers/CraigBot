from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from typing import TYPE_CHECKING

import discord
import yt_dlp
from youtube_search import YoutubeSearch

from audio.converter import convert_to_webm, equalise_loudness

if TYPE_CHECKING:
    from database.audio import Song

# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_download = {
#    'username': os.getenv('YT_USERNAME'),
#    'password': os.getenv('YT_PASSWORD'),
    'format': 'bestaudio[ext=webm]/best[ext=webm]/best',
    'outtmpl': os.path.join('data', 'audio_cache', '%(extractor)s-%(id)s.%(ext)s'),
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'usenetrc': True,
    'mark_watched': True
}

ytdl_info_only = {
#    'username': os.getenv('YT_USERNAME'),
#    'password': os.getenv('YT_PASSWORD'),
    'format': 'bestaudio[ext=webm]/best[ext=webm]/best',
    'restrictfilenames': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'usenetrc': True,
    'skip_download': True,
    'extract_flat': True
}

ffmpeg_options = {
    'options': '-vn',
}


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.title = data.get('title')
        self.url = data.get('webpage_url')
        self.thumbnail = data.get('thumbnail')
        self.channel_name = data.get('channel')
        self.duration_string = data.get('duration_string')
        self.duration = data.get('duration')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')

    @staticmethod
    def get_playlist(link):
        with yt_dlp.YoutubeDL(ytdl_info_only) as ydl:
            return ydl.extract_info(link)

    @staticmethod
    def download(song: Song) -> bool:
        with yt_dlp.YoutubeDL(ytdl_download) as ydl:
            try:
                info = ydl.extract_info(song.link)
            except yt_dlp.DownloadError as e:
                song.download_error = str(e)
                return False
            song.filename, song.extension = ydl.prepare_filename(info).rsplit('.', 1)
            song.filename = song.filename.rsplit('/')[-1]
            song.title = info['title']
            song.channel = info['channel']
            song.duration = info['duration']
            song.view_count = info['view_count']
            song.like_count = info['like_count']
            song.thumbnail = info['thumbnail']
            ydl.extract_info(song.link, download=True)
        
        if song.extension != 'webm':
            convert_to_webm(song)
        
        return True
