from typing import Union
from urllib.parse import parse_qs, urlparse

import yt_dlp
from youtube_search import YoutubeSearch


def extract_youtube_reference_from_url(url: str) -> Union[str, None]:
    parsed_url = urlparse(url)

    if "youtube.com" in parsed_url.netloc:
        parsed_query = parse_qs(parsed_url.query)
        return parsed_query.get("v", [None])[0]

    if "youtu.be" in parsed_url.netloc:
        return parsed_url.path.lstrip('/')

    return None


def ensure_youtube_reference(query: str) -> str:
    reference = extract_youtube_reference_from_url(query)
    if reference is None:
        search_results = YoutubeSearch(query, max_results=1).to_dict()
        if len(search_results) == 0:
            yt_dlp.utils.DownloadError('No results found.')
        reference = extract_youtube_reference_from_url(
            f"https://www.youtube.com{search_results[0]['url_suffix']}")
    return reference
