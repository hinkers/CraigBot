import os

from database.audio import Guild, Song, find_yt_dlp_file

LINK = 'https://www.youtube.com/watch?v=abc123'


def make_song(**overrides):
    fields = dict(reference='abc123', filename='youtube-abc123', extension='mp3')
    fields.update(overrides)
    return Song(**fields)


def test_link():
    assert make_song().link == LINK


def test_full_filename():
    assert make_song().full_filename == os.path.join('data', 'audio_cache', 'youtube-abc123.mp3')


def test_full_normalized_filename():
    assert make_song().full_normalized_filename == os.path.join('data', 'audio_cache', 'youtube-abc123_normalized.mp3')


def test_str_without_title_is_link():
    assert str(make_song()) == LINK


def test_str_with_title():
    assert str(make_song(title='Song')) == f'[Song]\n{LINK}'


def test_info():
    song = make_song(title='Song', channel='Chan', duration=215, view_count=10, like_count=2, thumbnail='http://img')

    assert song.info == dict(
        title='Song',
        webpage_url=LINK,
        thumbnail='http://img',
        channel='Chan',
        duration_string='215',
        duration=215,
        view_count=10,
        like_count=2,
    )


def test_guild_is_playing():
    assert Guild(id=1, now_playing_song_id=None).is_playing is False
    assert Guild(id=1, now_playing_song_id=5).is_playing is True


def test_find_prefers_finished_file(tmp_path):
    base = tmp_path / 'youtube-abc'
    (tmp_path / 'youtube-abc.webm.part').touch()
    (tmp_path / 'youtube-abc.m4a').touch()

    assert find_yt_dlp_file(str(base)) == f'{base}.m4a'


def test_find_falls_back_to_partial_download(tmp_path):
    base = tmp_path / 'youtube-abc'
    (tmp_path / 'youtube-abc.mp3.part').touch()

    assert find_yt_dlp_file(str(base)) == f'{base}.mp3.part'


def test_find_returns_none_when_nothing_downloaded(tmp_path):
    assert find_yt_dlp_file(str(tmp_path / 'youtube-abc')) is None


def test_delete_files_removes_audio_and_resets_flags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / 'data' / 'audio_cache'
    cache.mkdir(parents=True)
    (cache / 'youtube-abc123.mp3').touch()
    (cache / 'youtube-abc123_normalized.mp3').touch()
    song = make_song(is_downloaded=True, is_normalized=True)

    song.delete_files()

    assert list(cache.iterdir()) == []
    assert song.is_downloaded is False
    assert song.is_normalized is False


def test_delete_files_tolerates_missing_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    song = make_song(is_downloaded=True)

    song.delete_files()

    assert song.is_downloaded is False
