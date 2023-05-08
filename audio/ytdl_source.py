
import asyncio
import os
import re

import discord
import yt_dlp
from dotenv import load_dotenv
from youtube_search import YoutubeSearch

from audio.normalise import equalise_loudness

if os.getenv('craig_debug') == 'true':
    load_dotenv('dev.env')
else:
    load_dotenv('prod.env')

# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''


ytdl_download = {
    'username': os.getenv('YT_USERNAME'),
    'password': os.getenv('YT_PASSWORD'),
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
    'usenetrc': True,
    'mark_watched': True
}

ytdl_info_only = {
    'username': os.getenv('YT_USERNAME'),
    'password': os.getenv('YT_PASSWORD'),
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

        self.data = data
        self.is_search = data.get('is_search')

        self.title = data.get('title')
        self.url = data.get('webpage_url')
        self.thumbnail = data.get('thumbnail')
        self.channel_name = data.get('channel')
        self.duration = data.get('duration_string')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')

    @classmethod
    async def get_info(cls, query):
        is_search = False    
        youtube_pattern = r"^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$"
        if not bool(re.match(youtube_pattern, query)):
            is_search = True
            search_results = YoutubeSearch(query, max_results=1).to_dict()
            query = f"https://www.youtube.com{search_results[0]['url_suffix']}"
        
        with yt_dlp.YoutubeDL(ytdl_info_only) as ydl:
            info = ydl.extract_info(query, download=False)

        info['is_search'] = is_search
        info['is_playlist'] = info.get('playlist_count') is not None
        return info

    @classmethod
    async def download(cls, info):
        loop = asyncio.get_event_loop()

        if isinstance(info, str):
            info = await YTDLSource.get_info(info)

        try:
            with yt_dlp.YoutubeDL(ytdl_download) as ydl:
                filename = ydl.prepare_filename(info)

                if not os.path.exists(filename):
                    await loop.run_in_executor(None, lambda: ydl.extract_info(info.get('webpage_url'), download=True))
                    if info['duration'] <= 600:
                        equalise_loudness(filename)
                return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=info)
        except Exception:
            return None