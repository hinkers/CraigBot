from unittest.mock import patch

import pytest
import yt_dlp

from audio.audio import (ensure_youtube_reference,
                         extract_youtube_playlist_reference,
                         extract_youtube_reference_from_url)

VIDEO_ID = 'dQw4w9WgXcQ'


@pytest.mark.parametrize('url', [
    f'https://www.youtube.com/watch?v={VIDEO_ID}',
    f'https://youtube.com/watch?v={VIDEO_ID}&t=42s',
    f'https://www.youtube.com/watch?list=PL123&v={VIDEO_ID}',
    f'https://www.youtube.com/video/{VIDEO_ID}',
    f'https://youtu.be/{VIDEO_ID}',
    f'https://youtu.be/{VIDEO_ID}?si=shareToken',
])
def test_extracts_video_id(url):
    assert extract_youtube_reference_from_url(url) == VIDEO_ID


@pytest.mark.parametrize('url', ['https://example.com/watch?v=abc', 'never gonna give you up', ''])
def test_non_youtube_returns_none(url):
    assert extract_youtube_reference_from_url(url) is None


@pytest.mark.parametrize('link, expected', [
    ('https://www.youtube.com/playlist?list=PLabc_123-x', 'PLabc_123-x'),
    ('https://www.youtube.com/watch?v=abc&list=PLabc', 'PLabc'),
    ('https://www.youtube.com/playlist?list=PLabc&si=shareToken', 'PLabc'),
    ('https://www.youtube.com/watch?v=abc&list=PLabc&index=2', 'PLabc'),
])
def test_extracts_playlist_id(link, expected):
    assert extract_youtube_playlist_reference(link) == expected


@pytest.mark.parametrize('link', [
    'https://www.youtube.com/watch?v=abc',
    'https://example.com/?list=PLabc',
    'not a link',
])
def test_non_playlist_returns_none(link):
    assert extract_youtube_playlist_reference(link) is None


def test_ensure_reference_uses_url_without_searching():
    with patch('audio.audio.YoutubeSearch') as search:
        assert ensure_youtube_reference(f'https://youtu.be/{VIDEO_ID}') == VIDEO_ID
    search.assert_not_called()


def test_ensure_reference_searches_for_plain_text():
    with patch('audio.audio.YoutubeSearch') as search:
        search.return_value.to_dict.return_value = [{'id': 'found123'}]
        assert ensure_youtube_reference('some song') == 'found123'
    search.assert_called_once_with('some song', max_results=1)


def test_ensure_reference_raises_when_search_finds_nothing():
    with patch('audio.audio.YoutubeSearch') as search:
        search.return_value.to_dict.return_value = []
        with pytest.raises(yt_dlp.utils.DownloadError, match='No results found.'):
            ensure_youtube_reference('zzzz no such song')
