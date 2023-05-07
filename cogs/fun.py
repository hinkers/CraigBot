import discord
from discord.ext import commands

from utils.embedded_messages import magic_8_ball


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

    @commands.command(name="8ball")
    async def eight_ball(self, ctx, *, question: str=None):
        """ Ask the magic 8 ball. """
        if not question:
            await ctx.reply("You did not ask a valid question that can be correctly read.")
            return
        
        replies = [
            'It is certain', 'It is decidedly so', 'Without a doubt', 'Yes definitely', 'You may rely on it',
            'As I see it , yes', 'Most likely', 'Outlook good', 'Yes', 'Signs point to yes',
            'Reply hazy, try again', 'Ask again later', 'Better not tell you now', 'Cannot predict now',
            'Concentrate and ask again', 'Do not count on it', 'My reply is no', 'My sources say no',
            'Outlook not so good', 'Very doubtful'
        ]

        await ctx.send(**magic_8_ball(ctx.author.name, question, self.bot.random.choice(replies)))


async def setup(bot):
    await bot.add_cog(FunCog(bot))