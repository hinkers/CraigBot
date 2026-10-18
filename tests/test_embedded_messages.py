import pytest

from database.audio import Song
from utils import embedded_messages
from utils.embedded_messages import human_numbers


@pytest.mark.parametrize('number, expected', [
    (None, 0),
    (0, '0'),
    (999, '999'),
    (1500, '1K'),
    (2_500_000, '2M'),
    (3_000_000_000, '3B'),
])
def test_human_numbers(number, expected):
    assert human_numbers(number) == expected


def test_now_playing_embed():
    song = Song(
        reference='abc123', title='Song', channel='Chan', view_count=1500,
        like_count=20, duration=215, thumbnail='https://img.example/abc.jpg',
    )

    embed = embedded_messages.now_playing(song)

    assert embed.title == 'Song'
    assert embed.url == song.link
    assert embed.author.name == 'Now Playing'
    assert [(f.name, f.value) for f in embed.fields] == [
        ('Channel', 'Chan'), ('Views', '1K'), ('Likes', '20'), ('Duration', '215'),
    ]
    assert embed.footer.text


def test_queue_embed_numbers_songs():
    playing = Song(reference='now', title='Now')
    upcoming = [Song(reference='next1'), Song(reference='next2', title='Two')]

    embed = embedded_messages.queue(playing, upcoming)

    assert embed.description.splitlines() == [
        '**1) [Now]',
        'https://www.youtube.com/watch?v=now**',
        '2) https://www.youtube.com/watch?v=next1',
        '3) [Two]',
        'https://www.youtube.com/watch?v=next2',
    ]


def test_magic_8_ball_attaches_image():
    result = embedded_messages.magic_8_ball('tester', 'Will it work?', 'Yes')
    try:
        assert result['file'].filename == '8ball.png'
        embed = result['embed']
        assert [(f.name, f.value) for f in embed.fields] == [('tester asks', 'Will it work?'), ('Answer', 'Yes')]
        assert embed.thumbnail.url == 'attachment://8ball.png'
    finally:
        result['file'].close()
