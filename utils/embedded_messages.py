from datetime import datetime
from math import floor
from random import SystemRandom

import discord
from discord import Colour, Embed

from audio.ytdl_source import YTDLSource
from quotes import ferengi_rules_of_acquisition

random = SystemRandom()


def human_numbers(number):
    if number is None:
        return 0
    elif number < 1000:
        return str(number)
    elif number < 1000000:
        return str(int(number / 1000)) + "K"
    elif number < 1000000000:
        return str(int(number / 1000000)) + "M"
    return str(int(number / 1000000000)) + "B"


def random_footer():
    return random.choice(ferengi_rules_of_acquisition)


def now_playing(song):
    embed = Embed(
        title=song.title,
        description=song.link,
        url=song.link,
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
        value=song.channel,
        inline=True
    )
    embed.add_field(
        name='Views',
        value=human_numbers(song.view_count),
        inline=True
    )
    embed.add_field(
        name='Likes',
        value=human_numbers(song.like_count),
        inline=True
    )
    embed.add_field(
        name='Duration',
        value=song.duration,
        inline=True
    )
    embed.set_footer(text=random_footer())
    return embed


def queue(now_playing, songs):
    song_descriptions = [f'{n}) {s}' for n, s in enumerate(songs, start=2)]
    song_descriptions.insert(0, f'**1) {now_playing}**')
    embed = Embed(
        title='Queue',
        description='\n'.join(song_descriptions),
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