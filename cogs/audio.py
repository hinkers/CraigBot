import datetime
import glob
import os
import time
from typing import Optional, Union

import discord
import pytz
import yt_dlp
from discord.ext import commands, tasks
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

import audio.player as player
import utils.embedded_messages as embedded_messages
from audio.audio import ensure_youtube_reference
from audio.database import Guild, Queue, Song
from audio.tasks import download, equalise_loudness

time = datetime.time(hour=20, minute=12, tzinfo=pytz.timezone('Australia/Sydney'))


class AudioCog(commands.Cog, name='Audio'):
    def __init__(self, bot):
        self.bot = bot
        self.current_status = None
        bot.loop.create_task(self.initialize_tasks())

    async def initialize_tasks(self) -> None:
        await self.bot.wait_until_ready()
        await self.clear_queue(guild=None)
        await self.clear_now_playing(guild=None)
        self.listening_status.start()
        if not self.debug:
            self.delete_old_files.start()

    async def clear_queue(self, guild: Optional[Union[int, Guild]]) -> None:
        async with self.bot.session as session:
            statement = delete(Queue)
            if guild is not None:
                statement = statement.where(Queue.guild_id == getattr(guild, 'id', guild))

            await session.execute(statement)
            await session.commit()

    async def clear_now_playing(self, guild: Optional[Union[int, Guild]]) -> None:
        async with self.session as session:
            statement = select(Guild).where(Guild.now_playing_song_id != None)            
            if guild is not None:
                statement = statement.where(Guild.id == getattr(guild, 'id', guild))   
            result = await session.execute(statement)
            for guild in result.scalars():
                guild.now_playing_song_id = None
                guild.now_playing_started = None
            await session.commit()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user and after.channel is None:
            await self.clear_queue(before.channel.guild.id)
            await self.clear_now_playing(before.channel.guild.id)
        elif (
            member != self.bot.user
            and before.channel is not None
            and len(before.channel.members) == 1
            and before.channel.members[0] == self.bot.user
        ):
            voice_channel = discord.utils.get(self.bot.get_all_channels(), id=before.channel.id)
            if voice_channel is not None and isinstance(voice_channel, discord.VoiceChannel):
                voice_client = discord.utils.get(self.bot.voice_clients, channel=voice_channel)
                if voice_client is not None:
                    await voice_client.disconnect()

    @tasks.loop(seconds=10)
    async def listening_status(self): 
        new_status = None       
        async with self.bot.session as session:
            statement = select(Guild).where(Guild.now_playing_song_id != None).options(selectinload(Guild.song))
            result = await session.execute(statement)
            guild = result.scalar()

            if guild is not None:
                new_status = guild.song.title
            
        if self.current_status != new_status:
            await self.bot.wait_until_ready()
            await self.bot.change_presence(activity=discord.Game(name=new_status))
            self.current_status = new_status

    @tasks.loop(time=time)
    async def delete_old_files(self):
        now = time.time()
        for root, _, files in os.walk('data/audio_cache'):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if os.path.isfile(file_path):
                    modified_time = os.path.getmtime(file_path)
                    if (now - modified_time) > 2*30*24*60*60:  # 2 month = 2 * 30 days * 24 hours * 60 minutes * 60 seconds
                        try:
                            os.remove(file_path)
                            print(f"{file_path} file deleted.")
                        except Exception as e:
                            print(f"Error deleting {file_path}: {e}")

    @commands.hybrid_command(aliases=['summon'])
    async def connect(self, ctx: commands.context):
        """ Makes the bot join the current channel. """
        await ctx.send(f'Joined {ctx.author.voice.channel.name}')

    @commands.hybrid_command(aliases=['fuckoff', 'dc', 'kick'])
    async def disconnect(self, ctx: commands.context):
        """ Makes the bot leave the current channel. """        
        await ctx.voice_client.disconnect()
        await ctx.send('You got it chief.')
        await self.clear_queue(ctx.guild.id)

    @commands.hybrid_command(aliases=['stop'])
    async def skip(self, ctx: commands.context):
        """ Skip the current song. """
        if not player.skip(ctx):
            await ctx.send('Nothing is currently playing.')
            return
        if self.bot.random.randint(1, 10) == 1:
            await ctx.send(file=discord.File('data/images/skip_it.png'))
            return
        await ctx.send('Skipped.')

    @commands.hybrid_command()
    async def play(self, ctx: commands.context, *, query: str):
        """ Play a youtube music video in a voice channel. """
        await ctx.typing()

        try:
            reference = ensure_youtube_reference(query)
        except yt_dlp.utils.DownloadError as e:
            await ctx.send(str(e))

        async with self.bot.session as session:
            song = await Song.get_by_reference(session, reference)
            if song is None:
                song = Song(reference=reference)
                session.add(song)
                await session.commit()
                await session.refresh(song)
            
            await ctx.send(f'Added to queue: {song.link}')
            
            if not song.is_downloaded:
                try:
                    download.delay(song.id)
                except Exception as e:
                    print(e)
            elif not song.is_normalized:
                equalise_loudness.delay(song.id)
            
            guild = await Guild.ensure_guild(session=session, id_=ctx.guild.id, name=ctx.guild.name)
            guild.add_song_to_queue(song)
            await session.commit()

        await player.play(ctx)

    @commands.hybrid_command(aliases=['np', 'now', 'playing'])
    async def now_playing(self, ctx: commands.context):
        """ Displays what song is currently playing. """
        async with self.bot.session as session:
            statement = select(Guild).where(Guild.id == ctx.guild.id).options(selectinload(Guild.song))
            result = await session.execute(statement)
            guild = result.scalar()

        if guild is None or guild.song is None:
            await ctx.send('Nothing is currently playing.')
            return

        await ctx.send(embed=embedded_messages.now_playing(guild.song))

    @commands.hybrid_command()
    async def queue(self, ctx: commands.context):
        """ Displays all songs in the current queue. """
        async with self.bot.session as session:
            statement = select(Guild).where(Guild.id == ctx.guild.id).options(selectinload(Guild.song))
            result = await session.execute(statement)
            guild = result.scalar()

            if guild is None or guild.song is None:
                await ctx.send('Nothing is currently playing.')
                return

            statement = select(Queue).where(Queue.guild_id == ctx.guild.id).options(selectinload(Queue.song))
            result = await session.execute(statement)
            queues = result.scalars()

        await ctx.send(embed=embedded_messages.queue(guild.song, [q.song for q in queues]))

    @commands.hybrid_command()
    async def shuffle(self, ctx: commands.context):
        """ Displays all songs in the current queue. """
        audioplayer = self.bot.get_audioplayer(ctx.voice_client)
        audioplayer.queue.shuffle()

        await ctx.send('It\'s probably shuffled now')

    @commands.hybrid_command()
    @commands.is_owner()
    async def audio_cache(self, ctx: commands.context):
        """ List what audio files have been cached. """
        directory_path = os.path.join('data', 'audio_cache')

        files_count = len(os.listdir(directory_path))
        webm_count = len(glob.glob(os.path.join(directory_path, '*.webm')))
        json_count = len(glob.glob(os.path.join(directory_path, '*.json')))
        prenorm_count = len(glob.glob(os.path.join(directory_path, '*_prenorm.webm')))
        
        total_size = sum(os.path.getsize(os.path.join(directory_path, f)) for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))) / (1024 ** 2)

        oldest_date = float('inf')
        for filename in os.listdir(directory_path):
            filepath = os.path.join(directory_path, filename)
            if os.path.isfile(filepath):
                mod_time = os.path.getmtime(filepath)
                if mod_time < oldest_date:
                    oldest_date = mod_time
        oldest_date_str = datetime.datetime.fromtimestamp(oldest_date).strftime('%Y-%m-%d')

        lines = '\n'.join([
            f'Total files: {files_count}',
            f'Audio files: {webm_count}',
            f'Json files: {json_count}',
            f'Prenormalised files: {prenorm_count}',
            f'Total file size: {total_size:.2f} MiB',
            f'Oldest file: {oldest_date_str}'
        ])

        await ctx.send(f'```{lines}```')

    @connect.before_invoke
    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")

    @disconnect.before_invoke
    @skip.before_invoke
    @queue.before_invoke
    @shuffle.before_invoke
    async def requires_voice(self, ctx):
        if ctx.voice_client is None:
            await ctx.send("I am not in your channel.")
            raise commands.CommandError("Bot is not in your channel.")
        elif not ctx.author.voice:
            await ctx.send("You are not connected to a voice channel.")
            raise commands.CommandError("Author not connected to a voice channel.")


async def setup(bot):
    await bot.add_cog(AudioCog(bot))
