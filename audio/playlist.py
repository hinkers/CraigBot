from time import sleep

from audio.ytdl_source import YTDLSource


class Playlist:
    def __init__(self, data, loop):
        self.loop = loop
        self.task = None
        self.current_index = 0
        self.urls = [entry['url'] for entry in data['entries']]
        self.title = data['title']
        self.url = data['webpage_url']
        self.creator = data['uploader']
        self.availability = data['availability']
        self.thumbnail = data['thumbnails'][0]['url']
    
    def get(self):
        try:
            song = YTDLSource.load_json(self.urls[self.current_index])
        except FileNotFoundError:
            n = 0
            while not YTDLSource.check_cached(self.urls[self.current_index]) or n >= 20:
                sleep(1)
                n += 1
        except IndexError:
            return None
        self.current_index += 1
        self.ensure_next_downloaded()
        return song
    
    async def download_index(self, index):
        try:
            return await YTDLSource.download(self.urls[index])
        except IndexError:
            pass

    def ensure_next_downloaded(self):
        self.task = self.loop.create_task(self.download_index(self.current_index))
