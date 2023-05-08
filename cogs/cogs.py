import glob
import os
from typing import Literal, Optional

from discord.ext import commands


class CogsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def coggers(self, ctx: commands.Context, command: Optional[Literal["load", "unload", "reload"]] = None, cog: Optional[str] = None) -> None:
        """ Manage cogs. """
        all_files = [f.replace('/', '.')[:-3] for f in glob.glob(os.path.join('cogs', '*.py'))]
        all_files.sort()
        cog_names = [tpl[0] for tpl in self.bot.coggers]
        if command is None:
            loaded = [f':white_check_mark: {f}' if f in cog_names else f':x: {f}' for f in all_files]
            await ctx.send('\n'.join(loaded))
            return

        if cog is None:
            await ctx.send(f'Missing cog name.')
        elif not cog in all_files:
            await ctx.send(f'Unkown cog `{cog}`')
        elif command == "load":
            try:
                await self.bot.load_extension(cog)
                self.bot.coggers.append((cog, list(self.bot.cogs.values())[-1].qualified_name))
                await ctx.send(f'Loaded `{cog}`')
            except Exception as e:
                await ctx.send(f'Failed to load `{cog}`.\n{e}')
        elif command == "unload":
            if cog == 'cogs.cogs':
                await ctx.send(f'Don\'t be stupid.')
                return
            try:
                await self.bot.unload_extension(cog)
                self.bot.coggers = [tpl for tpl in self.bot.coggers if tpl[0] != cog]
                await ctx.send(f'Unloaded `{cog}`')
            except Exception as e:
                await ctx.send(f'Failed to remove `{cog}`.\n{e}')
        elif command == "reload":
            try:
                await self.bot.reload_extension(cog)
                if not cog in cog_names:
                    self.bot.coggers.append((cog, list(self.bot.cogs.values())[-1].qualified_name))
                await ctx.send(f'Reloaded `{cog}`')
            except Exception as e:
                await ctx.send(f'Failed to reload `{cog}`.\n{e}')


async def setup(bot):
    await bot.add_cog(CogsCog(bot))