
import asyncio
import os
import re

import discord
import yt_dlp as youtube_dl
from youtube_search import YoutubeSearch

from audio.normalise import equalise_loudness

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
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
    "usenetrc": True,
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

ffmpeg_options = {
    'options': '-vn',
}


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, is_search, volume=0.5):
        super().__init__(source, volume)

        self.data = data
        self.is_search = is_search

        self.title = data.get('title')
        self.url = data.get('webpage_url')
        self.thumbnail = data.get('thumbnail')
        self.channel_name = data.get('channel')
        self.duration = data.get('duration_string')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')

    @classmethod
    async def from_youtube(cls, query, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        is_search = False
        youtube_pattern = r"^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$"
        if not bool(re.match(youtube_pattern, query)):
            is_search = True
            search_results = YoutubeSearch(query, max_results=1).to_dict()
            query = f"https://www.youtube.com{search_results[0]['url_suffix']}"
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        except youtube_dl.utils.DownloadError:
            return None
        if 'entries' in data:
            data = data['entries'][0]
        filename = ytdl.prepare_filename(data)

        if not os.path.exists(filename):
            await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=True))
            if data['duration'] <= 600:
                equalise_loudness(filename)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, is_search=is_search)