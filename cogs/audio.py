import discord
from discord.ext import commands

import utils.embedded_messages as embedded_messages
from audio.ytdl_source import YTDLSource


class AudioCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user and after.channel is None:
            self.bot.destroy_audioplayer(before.channel)
        elif (
            member != self.bot.user
            and before.channel is not None
            and len(before.channel.members) == 1
            and before.channel.members[0] == self.bot.user
        ):
            voice_client = self.bot.get_channel_voice_client(before.channel)
            await voice_client.disconnect()

    @commands.hybrid_command()
    async def summon(self, ctx: commands.context):
        """ Makes the bot join the current channel. """
        await ctx.send(f'Joined {ctx.author.voice.channel.name}')

    @commands.hybrid_command()
    async def fuckoff(self, ctx: commands.context):
        """ Makes the bot leave the current channel. """        
        await ctx.voice_client.disconnect()
        await ctx.send('You got it chief.')

    @commands.hybrid_command()
    async def skip(self, ctx: commands.context):
        """ Skip the current song. """
        audioplayer = self.bot.get_audioplayer(ctx.voice_client)
        if not audioplayer.is_playing:
            await ctx.send('Nothing is currently playing.')
            return
        audioplayer.skip()
        if self.bot.random.randint(1, 10) == 1:
            await ctx.send(file=discord.File('data/images/skip_it.png'))
            return
        await ctx.send('Skipped.')

    @commands.hybrid_command()
    async def play(self, ctx: commands.context, *, query: str):
        """ Play a youtube music video in a voice channel. """
        await ctx.typing()

        info = await YTDLSource.get_info(query)
        if not info['is_playlist'] and info['duration'] > 900:
            await ctx.send(f'Large download detected, this file will be queued as soon as it is finished downloading.')
        
        if info['is_playlist']:
            source = await YTDLSource.download(info['entries'][0]['url'])
        else:
            source = await YTDLSource.download(info)
        if source is None:
            await ctx.send(f'Failed to download audio track.')
            return

        audioplayer = self.bot.get_audioplayer(ctx.voice_client)
        audioplayer.add_song(source)

        if not info['is_playlist']:
            await ctx.send(
                embed=embedded_messages.queued(
                    source,
                    ctx.author.mention,
                    query,
                    not audioplayer.is_playing
                )
            )
            audioplayer.play()
        else:
            await ctx.send(
                embed=embedded_messages.playlist(
                    info,
                    ctx.author.mention,
                    query
                )
            )
            audioplayer.play()

            success = 0
            skipped = 0
            for song in info['entries'][1::]:
                source = await YTDLSource.download(song['url'])
                if source is not None:
                    audioplayer.add_song(source)
                    skipped += 1
                success += 1
            print(success, skipped)
            success -= skipped
            print(success, skipped)
            await ctx.send(
                embed=embedded_messages.playlist_finished(
                    info,
                    success,
                    skipped,
                    ctx.author.mention,
                    query
                )
            )

    @commands.hybrid_command()
    async def np(self, ctx: commands.context):
        """ Displays what song is currently playing. """
        audioplayer = self.bot.get_audioplayer(ctx.voice_client)
        if not audioplayer.is_playing:
            await ctx.send('Nothing is currently playing.')
            return

        await ctx.send(embed=embedded_messages.now_playing(audioplayer.current_song))

    @commands.hybrid_command()
    async def queue(self, ctx: commands.context):
        """ Displays all songs in the current queue. """
        audioplayer = self.bot.get_audioplayer(ctx.voice_client)
        if not audioplayer.is_playing:
            await ctx.send('Nothing is currently playing.')
            return

        await ctx.send(
            embed=embedded_messages.queue(audioplayer.current_song, audioplayer.get_queue())
        )
    
    @summon.before_invoke
    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
    
    @fuckoff.before_invoke
    @skip.before_invoke
    @queue.before_invoke
    async def requires_voice(self, ctx):
        if ctx.voice_client is None:
            await ctx.send("I am not in your channel.")
            raise commands.CommandError("Bot is not in your channel.")
        elif not ctx.author.voice:
            await ctx.send("You are not connected to a voice channel.")
            raise commands.CommandError("Author not connected to a voice channel.")


async def setup(bot):
    await bot.add_cog(AudioCog(bot))
