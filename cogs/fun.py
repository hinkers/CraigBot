import discord
from discord.ext import commands


class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    async def lettuce(self, ctx: commands.context):
        """ Generate a random funny joke. """
        await ctx.send(file=discord.File('data/images/lettuce.png'))

    @commands.hybrid_command()
    async def rules(self, ctx: commands.context):
        """ Displays the server rules. """
        await ctx.send(file=discord.File('data/images/rules.jpg'))


async def setup(bot):
    await bot.add_cog(FunCog(bot))