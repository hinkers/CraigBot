
class Queue:

    def __init__(self):
        self._queue = []
    
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
    
    @property
    def is_playing(self):
        return self.current_song is not None

    def add_song(self, source):
        self.queue.put(source)

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
    
        song = self.queue.get()
        self.voice_client.play(
            song,
            after=self.next_song
        )
        self.current_song = song
    
    def skip(self):
        self.voice_client.stop()

    def get_queue(self):
        return self.queue.as_list()
