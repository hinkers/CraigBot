import math
from typing import Literal, Optional

import discord
from discord.ext import commands

from database.database import Base, get_engine


class AdminCog(commands.Cog, name='Admin'):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        id_str = f' Logged in with ID: {self.bot.user.id} '
        l = (len(id_str) - len(self.bot.user.name)) / 2
        print('\n╭' + ('─' * math.floor(l)) + self.bot.user.name + ('─' * math.ceil(l)) + '╮')
        print(f'│{id_str}│')
        print('╰' + ('─' * len(id_str)) + '╯')

    @commands.hybrid_command(aliases=['sudoku', 'restart'])
    @commands.has_role(578752587172675596)  # Koi Boiz
    async def kill(self, ctx: commands.Context) -> None:
        """ Kill the bot. """
        await ctx.send(file=discord.File('data/images/snap.gif'))
        await ctx.bot.close()

    @commands.hybrid_command()
    async def ping(self, ctx: commands.Context) -> None:
        """ Responds pong. """
        await ctx.send("pong", ephemeral=True)

    @commands.hybrid_command(description='[~] Syncs to the guild\n[*] Syncs global to the guild\n[^] Clears first, then syncs to the guild\nLeave blank for a global sync')
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        """ Syncs the application commands. """
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()
            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return
        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1
        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.command()
    @commands.dm_only()
    @commands.is_owner()
    async def say(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str):
        await channel.send(message)

    @commands.command()
    @commands.dm_only()
    @commands.is_owner()
    async def reply(self, ctx: commands.Context, original_message: discord.Message, *, message: str):
        await original_message.reply(message)

    @commands.command()
    @commands.dm_only()
    @commands.is_owner()
    async def create_tables(self, ctx: commands.Context) -> None:
        with get_engine(async_=False).begin() as engine:
            Base.metadata.create_all(bind=engine)
        await ctx.send('Tables created')

async def setup(bot):
    await bot.add_cog(AdminCog(bot))