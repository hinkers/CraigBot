from datetime import datetime

from discord import Colour, Embed
from random import SystemRandom
from quotes import quotes

random = SystemRandom()


def human_numbers(number):
    if number < 1000:
        return str(number)
    elif number < 1000000:
        return str(int(number / 1000)) + "K"
    elif number < 1000000000:
        return str(int(number / 1000000)) + "M"
    return str(int(number / 1000000000)) + "B"


def random_footer():
    return random.choice(quotes)


def queued(song, author, query, now_playing=False):
    embed = Embed(
        title=song.title,
        url=song.url,
        description=(
            f'Added by {author}, using search term(s) "{query}".'
            if song.is_search else
            f'Added by {author} with a direct link.'
        ),
        colour=Colour.teal(),
        timestamp=datetime.now()
    )
    if now_playing:
        embed.set_author(
            name='Now Playing',
            icon_url='https://www.youtube.com/s/desktop/066935b0/img/favicon_32x32.png'
        )
    else:
        embed.set_author(
            name='Queued',
            icon_url='https://www.youtube.com/s/desktop/066935b0/img/favicon_32x32.png'
        )
    embed.set_thumbnail(url=song.thumbnail)
    embed.add_field(
        name='Channel',
        value=song.channel_name,
        inline=True
    )
    embed.add_field(
        name='Views',
        value=human_numbers(song.views),
        inline=True
    )
    embed.add_field(
        name='Likes',
        value=human_numbers(song.likes),
        inline=True
    )
    embed.add_field(
        name='Duration',
        value=song.duration,
        inline=True
    )
    embed.set_footer(text=random_footer())
    return embed


def now_playing(song):
    embed = Embed(
        title=song.title,
        url=song.url,
        colour=Colour.teal(),
        timestamp=datetime.now()
    )
    embed.set_author(
        name='Now Playing',
        icon_url='https://www.youtube.com/s/desktop/066935b0/img/favicon_32x32.png'
    )
    embed.set_thumbnail(url=song.thumbnail)
    embed.add_field(
        name='Channel',
        value=song.channel_name,
        inline=True
    )
    embed.add_field(
        name='Views',
        value=human_numbers(song.views),
        inline=True
    )
    embed.add_field(
        name='Likes',
        value=human_numbers(song.likes),
        inline=True
    )
    embed.add_field(
        name='Duration',
        value=song.duration,
        inline=True
    )
    embed.set_footer(text=random_footer())
    return embed


def queue(now_playing, queue):
    songs = [f'1) [{now_playing.title}]({now_playing.url}) [{now_playing.duration}]']
    for n, song in enumerate(queue[:19], start=2):
        songs.append(f'{n}) [{song.title}]({song.url}) [{song.duration}]')
    embed = Embed(
        title='Queue',
        description='\n'.join(songs),
        colour=Colour.teal(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=random_footer())
    return embed
