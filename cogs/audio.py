import asyncio
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
from sqlalchemy.sql import func

import audio.player as player
import utils.embedded_messages as embedded_messages
from audio.audio import (ensure_youtube_reference,
                         extract_youtube_playlist_reference)
from audio.tasks import download, equalise_loudness
from audio.ytdl_source import YTDLSource
from database.audio import Favourite, Guild, Queue, Song

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
        if not self.bot.debug:
            self.delete_old_files.start()

    @commands.is_owner()
    async def clear_queue(self, guild: Optional[Union[int, Guild]]) -> None:
        async with self.bot.session as session:
            statement = delete(Queue)
            if guild is not None:
                statement = statement.where(Queue.guild_id == getattr(guild, 'id', guild))

            await session.execute(statement)
            await session.commit()

    @commands.is_owner()
    async def clear_now_playing(self, guild: Optional[Union[int, Guild]]) -> None:
        async with self.bot.session as session:
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
        """
        Asynchronously deletes files associated with Song records that were downloaded but not played in the last two months.
        It also updates the corresponding records in the database to reflect the changes.
        """

        # Calculate the date two months ago from the current time
        two_months_ago = datetime.datetime.now() - datetime.timedelta(days=60)

        # Start an asynchronous database session
        async with self.bot.session as session:
            # Prepare a SQL query to select songs that are downloaded and not played for the last two months
            statement = select(Song).where(
                Song.is_downloaded == True,
                Song.date_last_played < two_months_ago
            )

            # Execute the query asynchronously
            result = await session.execute(statement)

            # Iterate over the results
            for song in result.scalars():
                try:
                    # If the main song file exists, delete it
                    if os.path.isfile(song.file_path):
                        os.remove(song.file_path)

                    # If the normalized version of the song exists, delete it
                    if os.path.isfile(song.full_normalized_filename):
                        os.remove(song.full_normalized_filename)

                    # Update the song record to reflect the deletion
                    song.is_downloaded = False
                    song.is_normalized = False

                except Exception as e:
                    # Log any exceptions encountered during file deletion
                    print(f"Error deleting files for song {song.id}: {e}")

            # Commit the changes to the database after processing all songs
            await session.commit()

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

    @commands.hybrid_command(aliases=['stop', 'next'])
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
            return

        async with self.bot.session as session:
            song = await Song.get_by_reference(session, reference)
            if song is None:
                song = Song(reference=reference)
                session.add(song)
                await session.commit()
                await session.refresh(song)
            
            await self.do_play(ctx, song, session)

    @commands.hybrid_command()
    async def playf(self, ctx: commands.context, *, name: str):
        """ Play a youtube music video in a voice channel. """
        await ctx.typing()

        async with self.bot.session as session:
            statement = select(Favourite).where(Favourite.name == name, Favourite.user_id == ctx.author.id).options(selectinload(Favourite.song))
            result = await session.execute(statement)
            favourite = result.scalar()
            if not favourite:
                await ctx.send(f'Favourite not found.')
                return
            song = favourite.song
            
            await self.do_play(ctx, song, session)

    @commands.hybrid_command()
    async def playlist(self, ctx: commands.context, *, link: str):
        """ Play a youtube music video in a voice channel. """
        await ctx.typing()

        reference = extract_youtube_playlist_reference(link)
        if reference is None:
            await ctx.send('Not a valid youtube playlist link.')
            return

        playlist_info = YTDLSource.get_playlist(f'https://www.youtube.com/playlist?list={reference}')

        async with self.bot.session as session:
            guild = await Guild.ensure_guild(session=session, id_=ctx.guild.id, name=ctx.guild.name)
            result = await session.execute(
                select(func.max(Queue.order_id)).where(Queue.guild_id == guild.id)
            )
            max_order_id = result.scalar_one_or_none()
            order_id = max_order_id if max_order_id else 0
            
            first = True
            for song_dict in playlist_info['entries']:
                order_id += 1
                song = await Song.get_by_reference(session, song_dict['id'])
                if song is None:
                    song = Song(reference=song_dict['id'])
                    session.add(song)
                    await session.commit()
                    await session.refresh(song)
                
                if first:
                    first = False            
                    await self.do_play(ctx, song, session)
                    await asyncio.sleep(10)
                    continue
                
                queue = guild.add_song_to_queue(session, song)
                queue.order_id = order_id

            await session.commit()

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

            statement = (
                select(Queue)
                .where(Queue.guild_id == ctx.guild.id)
                .options(selectinload(Queue.song))
                .order_by(Queue.order_id)
                .limit(19)
            )
            result = await session.execute(statement)
            queues = result.scalars()

        await ctx.send(embed=embedded_messages.queue(guild.song, [q.song for q in queues]))

    @commands.hybrid_command()
    async def shuffle(self, ctx: commands.context):
        """ Shuffle the play order of all songs in the current queue. """
        async with self.bot.session as session:
            statement = select(Queue).where(Queue.guild_id == ctx.guild.id)
            result = await session.execute(statement)
            queue = result.scalars().all()

            self.bot.random.shuffle(queue)
            for n, queue_item in enumerate(queue):
                queue_item.order_id = n

            await session.commit()

        await ctx.send('It\'s probably shuffled now')

    @commands.hybrid_command()
    @commands.is_owner()
    async def audio_cache(self, ctx: commands.context):
        """ List what audio files have been cached. """
        directory_path = os.path.join('data', 'audio_cache')

        files_count = len(os.listdir(directory_path))
        webm_count = len(glob.glob(os.path.join(directory_path, '*.webm')))
        
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
            f'Total file size: {total_size:.2f} MiB',
            f'Oldest file: {oldest_date_str}'
        ])

        await ctx.send(f'```{lines}```')

    @commands.hybrid_group(invoke_without_command=False, aliases=['favourites'])
    async def favourite(self, ctx):
        await ctx.send('\n'.join([
            '```Commands:',
            '   - favourite add <url> <name>',
            '   - favourite delete <url> <name>',
            '   - favourite list',
            '   - playf name',
            '```'
        ]))

    @favourite.command(name='add')
    @commands.has_permissions(manage_messages=True)
    async def favourite_add(self, ctx, query: str, *, name: str):
        async with self.bot.session as session:
            statement = select(Favourite).where(Favourite.user_id == ctx.author.id, Favourite.name == name)
            result = await session.execute(statement)
            favourite = result.scalar()

            if favourite:
                await ctx.send('Favourite name already exists.')
            else:
                reference = ensure_youtube_reference(query)
                song = await Song.get_by_reference(session, reference)
                if song is None:
                    song = Song(reference=reference)
                    session.add(song)
                    await session.commit()
                    await session.refresh(song)

                favourite = Favourite(
                    user_id=ctx.author.id,
                    song_id=song.id,
                    name=name
                )
                session.add(favourite)
                await session.commit()
                await ctx.send(f'Favourite `{name}` added.')

    @favourite.command(name='delete')
    @commands.has_permissions(manage_messages=True)
    async def favourite_delete(self, ctx, *, name: str):
        async with self.bot.session as session:
            statement = select(Favourite).where(Favourite.user_id == ctx.author.id, Favourite.name == name)
            result = await session.execute(statement)
            favourite = result.scalar()

            if favourite:
                await session.delete(favourite)
                await session.commit()
                await ctx.send(f'Favourite `{name}` deleted.')
            else:
                await ctx.send('Favourite not found.')

    @favourite.command(name='list')
    async def favourite_list(self, ctx):
        async with self.bot.session as session:
            statement = select(Favourite).where(Favourite.user_id == ctx.author.id)
            result = await session.execute(statement)
            favourites = result.scalars().all()

            if favourites:
                descriptions = [f'- {t.name}' for t in favourites]
                await ctx.send('```All your favourites:\n' + '\n'.join(descriptions) + '```')
            else:
                await ctx.send('No favourites available.')

    @connect.before_invoke
    @play.before_invoke
    @playf.before_invoke
    @playlist.before_invoke
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

    async def do_play(self, ctx, song, session):
        if not song.is_downloaded:
            song.has_download_task = True
            await session.commit()
            download.delay(song.id)
        elif not song.is_normalized:
            equalise_loudness.delay(song.id)
        
        guild = await Guild.ensure_guild(session=session, id_=ctx.guild.id, name=ctx.guild.name)
        queue = guild.add_song_to_queue(session, song)
        result = await session.execute(
            select(func.max(Queue.order_id)).where(Queue.guild_id == queue.guild_id)
        )
        max_order_id = result.scalar_one_or_none()
        queue.order_id = max_order_id + 1 if max_order_id else 1
        await session.commit()
        
        await ctx.send(f'Added to queue: {song}')

        await player.play(ctx)


async def setup(bot):
    await bot.add_cog(AudioCog(bot))
