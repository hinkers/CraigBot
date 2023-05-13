from datetime import datetime
from random import SystemRandom

import discord
from discord import Colour, Embed
from audio.playlist import Playlist
from audio.ytdl_source import YTDLSource

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
        value=song.duration_string,
        inline=True
    )
    embed.set_footer(text=random_footer())
    return embed


def playlist(playlist, author, link):
    embed = Embed(
        title=playlist.title,
        url=link,
        description=f'Added by {author}, items will downloaded in the background and be added to the queue as they finish.',
        colour=Colour.teal(),
        timestamp=datetime.now()
    )
    embed.set_author(
        name='Playlist',
        icon_url='https://www.youtube.com/s/desktop/066935b0/img/favicon_32x32.png'
    )
    embed.set_thumbnail(url=playlist.thumbnail)
    embed.add_field(
        name='Creator',
        value=playlist.creator,
        inline=True
    )
    embed.add_field(
        name='Availability',
        value=playlist.availability.title(),
        inline=True
    )
    embed.add_field(
        name='Playlist Items',
        value=len(playlist.urls),
        inline=True
    )
    embed.set_footer(text=random_footer())
    return embed


def now_playing(song, song_time):
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
        name='Current Place',
        value=song_time,
        inline=True
    )
    embed.add_field(
        name='Duration',
        value=song.duration_string,
        inline=True
    )
    embed.set_footer(text=random_footer())
    return embed


def queue(now_playing, queue):
    songs = [f'1) [{now_playing.title}]({now_playing.url}) [{now_playing.duration_string}]']
    for n, song_url in enumerate(queue[:19], start=2):
        if isinstance(song_url, Playlist):
            pl = song_url
            songs.append(f'{n}) [{pl.title}]({pl.url}) [Playlist {len(pl.urls) - pl.current_index} songs]')
            continue
        song = YTDLSource.load_json(song_url)
        songs.append(f'{n}) [{song.title}]({song.url}) [{song.duration_string}]')
    if len(queue) > 20:
        songs.append(f'\n{len(queue)} total songs queued.')
    embed = Embed(
        title='Queue',
        description='\n'.join(songs),
        colour=Colour.teal(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=random_footer())
    return embed


def magic_8_ball(author, question, answer):
    embed = Embed(
            title='Magic 8 Ball',
            color=0x0b0d5e,
    )
    embed.add_field(name=f"{author} asks", value=question, inline=False)
    embed.add_field(name="Answer", value=answer, inline=False)
    embed.set_thumbnail(url="attachment://8ball.png")
    embed.set_footer(text=random_footer())
    image = discord.File("data/images/8ball.png", filename="8ball.png")
    return dict(file=image, embed=embed)