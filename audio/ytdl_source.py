
import asyncio
import os
import re
import json
import discord
import yt_dlp
from youtube_search import YoutubeSearch

from audio.converter import convert_to_webm, equalise_loudness

from datetime import datetime

from audio.database import Song

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

        self.is_search = data.get('is_search')

        self.title = data.get('title')
        self.url = data.get('webpage_url')
        self.thumbnail = data.get('thumbnail')
        self.channel_name = data.get('channel')
        self.duration_string = data.get('duration_string')
        self.duration = data.get('duration')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.is_playlist = data.get('is_playlist')
        self.is_cached = True

        cached = data.get('cached')
        if cached is None:
            self.is_cached = False
            cached = self.save_json()

        cached_dt = datetime.fromtimestamp(cached) 
        if cached_dt.date() != datetime.now().date():
            cached_dt = datetime.fromtimestamp(self.save_json()) 

        self.cached_dt = cached_dt

    def as_dict(self):        
        cached = datetime.now().timestamp()
        return dict(
            is_search=self.is_search,
            title=self.title,
            webpage_url=self.url,
            thumbnail=self.thumbnail,
            channel=self.channel_name,
            duration_string=self.duration_string,
            duration=self.duration,
            view_count=self.views,
            like_count=self.likes,
            is_playlist=self.is_playlist,
            cached=cached
        )

    def save_json(self):
        filename = os.path.join('data', 'audio_cache', 'youtube-' + self.url.rsplit('=')[-1])
        data = self.as_dict()
        with open(filename + '.json', 'w+') as f:
            json.dump(data, f)
        dt_epoch = datetime.now().timestamp()
        os.utime(filename + '.webm', (dt_epoch, dt_epoch))
        return data['cached']
    
    @staticmethod
    def is_youtube_link(link):
        youtube_pattern = r"^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$"
        if isinstance(link, str) and bool(re.match(youtube_pattern, link)):
            return True
        return False
    
    @staticmethod
    def get_cached_filename(link):
        if '?' not in link:
            return ''
        query_string = link.split('?')[1]
        query_params = query_string.split('&')
        for param in query_params:
            if param.startswith('v='):
                return os.path.join('data', 'audio_cache', 'youtube-' + param[2:])
        return ''

    @staticmethod
    def check_cached(link):
        if not YTDLSource.is_youtube_link(link):
            return False
        filename = YTDLSource.get_cached_filename(link)
        if os.path.isfile(filename + '.webm') and os.path.isfile(filename + '.json'):
            return True
        return False

    @classmethod
    def load_json(cls, filename):
        if YTDLSource.is_youtube_link(filename):
            filename =  YTDLSource.get_cached_filename(filename)
        with open(filename + '.json', 'r') as f:
            return cls(discord.FFmpegPCMAudio(filename + '.webm', **ffmpeg_options), data=json.load(f))

    @classmethod
    async def get_info(cls, query):
        is_search = False    
        if not YTDLSource.is_youtube_link(query):
            is_search = True
            search_results = YoutubeSearch(query, max_results=1).to_dict()
            if len(search_results) == 0:
                yt_dlp.utils.DownloadError('No results found.')
            query = f"https://www.youtube.com{search_results[0]['url_suffix']}"
        
        if YTDLSource.check_cached(query):
            return YTDLSource.load_json(query).as_dict()
        
        try:
            with yt_dlp.YoutubeDL(ytdl_info_only) as ydl:
                info = ydl.extract_info(query, equalise_loudness=False)
        except yt_dlp.utils.DownloadError as e:
            print(e)
            pass  # Something about a playlist does not exist, look into radios

        info['is_search'] = is_search
        info['is_playlist'] = info.get('playlist_count') is not None
        return info

    @classmethod
    async def old_download(cls, info):
        loop = asyncio.get_event_loop()

        if isinstance(info, str):
            if YTDLSource.check_cached(info):
                return YTDLSource.load_json(info)
            info = await YTDLSource.get_info(info)

        if YTDLSource.check_cached(info.get('webpage_url')):
            return YTDLSource.load_json(info.get('webpage_url'))

        try:
            with yt_dlp.YoutubeDL(ytdl_download) as ydl:
                filename = ydl.prepare_filename(info)

                if not os.path.exists(filename.rsplit('.')[0] + '.webm'):
                    await loop.run_in_executor(None, lambda: ydl.extract_info(info.get('webpage_url'), download=True))
                    if not filename.endswith('.webm') and os.path.exists(filename):
                        convert_to_webm(filename)
                    if info['duration'] <= 600:
                        equalise_loudness(filename)
                return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=info)
        except Exception as e:
            return None

    @classmethod
    async def download(cls, song: Song) -> None:
        with yt_dlp.YoutubeDL(ytdl_download) as ydl:
            song.filename, song.extension = ydl.prepare_filename(song.info).rsplit('.', 1)
            ydl.extract_info(song.link, download=True)
        
        if song.extension != 'webm':
            convert_to_webm(song)
