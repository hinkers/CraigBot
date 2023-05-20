
from datetime import datetime

from audio.playlist import Playlist
from audio.ytdl_source import YTDLSource


class Queue:

    def __init__(self):
        self._queue = []
    
    def insert(self, index, item):
        self._queue.insert(index, item)

    def put(self, item):
        self._queue.append(item)
    
    def get(self):
        return self._queue.pop(0)

    def is_empty(self):
        return len(self._queue) == 0

    def as_list(self):
        return self._queue


class AudioPlayer:

    def __init__(self, voice_client):
        self.voice_client = voice_client
        self.queue = Queue()
        self.current_song = None
        self.current_song_datetime = None
    
    @property
    def is_playing(self):
        return self.current_song is not None

    @property
    def current_song_time(self):
        if self.current_song_datetime is None:
            return None
        time_delta = datetime.now() - self.current_song_datetime
        hours, remainder = divmod(time_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours == 0:
            return f"{minutes:02d}:{seconds:02d}"
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def add_song(self, source):
        if isinstance(source, Playlist):
            self.queue.put(source)
            return
        self.queue.put(source.url)

    def play(self):
        if self.is_playing:
            return
        self.next_song()

    def next_song(self, error=None):
        if error:
            print(error)

        if self.queue.is_empty():
            self.current_song = None
            return
    
        next_item = self.queue.get()
        if isinstance(next_item, Playlist):
            song = next_item.get()
            if song is None:
                return self.next_song()
            self.queue.insert(0, next_item)
        else:
            song = YTDLSource.load_json(next_item)
        self.voice_client.play(
            song,
            after=self.next_song
        )
        self.current_song = song
        self.current_song_datetime = datetime.now()

    def skip(self):
        self.voice_client.stop()

    def get_queue(self):
        return self.queue.as_list()
