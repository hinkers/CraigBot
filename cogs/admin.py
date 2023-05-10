import math
from typing import Literal, Optional

import discord
from discord.ext import commands


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

    @commands.hybrid_command()
    async def sudoku(self, ctx: commands.Context) -> None:
        """ Commit sudoku. """
        await ctx.send(file=discord.File('data/images/snap.gif'))
        await ctx.bot.close()

    @commands.hybrid_command()
    async def ping(self, ctx: commands.Context) -> None:
        """ Responds pong. """
        await ctx.send("pong", ephemeral=True)

    @commands.command()
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


async def setup(bot):
    await bot.add_cog(AdminCog(bot))