import asyncio
from datetime import datetime

from discord import FFmpegPCMAudio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, sessionmaker

from audio.database import Guild, Queue, get_engine
from audio.ytdl_source import YTDLSource, ffmpeg_options

Session = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=get_engine(), class_=AsyncSession)


async def play(ctx):
    async with Session() as session:
        guild = await Guild.ensure_guild(session, ctx.guild.id, ctx.guild.name)
    if guild.is_playing:
        return
    next_song(ctx)


def skip(ctx) -> bool:
    voice_client = ctx.voice_client
    if voice_client.is_playing:
        voice_client.stop()  # For some reason this doesn't seem to trigger the next song
        return True
    return False


def next_song(ctx, error=None):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.create_task(async_next_song(ctx, error))


async def async_next_song(ctx, error=None):
    if error:
        print(error)

    async with Session() as session:        
        voice_client = ctx.voice_client
        guild = await Guild.ensure_guild(session, ctx.guild.id, ctx.guild.name)

        # Get next queue item
        statement = select(Queue).where(Queue.guild_id == guild.id).order_by(Queue.id).options(selectinload(Queue.song))
        result = await session.execute(statement)
        next_in_queue = result.scalar()

        if not next_in_queue:
            guild.now_playing_song_id = None
            guild.now_playing_started = None
            await session.commit()
            return
    
        song = next_in_queue.song
        await session.delete(next_in_queue)

        while not song.is_downloaded:
            await asyncio.sleep(1)
            await session.refresh(song)

        voice_client.play(
            YTDLSource(FFmpegPCMAudio(song.full_filename, **ffmpeg_options), data=song.info),
            after=lambda e: next_song(ctx, e)
        )

        guild.now_playing_song_id = song.id
        guild.now_playing_started = datetime.now()
        await session.commit()
