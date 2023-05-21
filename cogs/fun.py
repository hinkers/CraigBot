import discord
from discord.ext import commands

from utils.embedded_messages import magic_8_ball


class FunCog(commands.Cog, name='Fun'):
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

    @commands.hybrid_command(name="8ball")
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

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            if self.bot.random.randint(1, 100) == 7:
                await message.add_reaction(self.bot.craigmoment)

            words = message.content.lower().replace('?', '').replace('\'', '').split(' ')

            if 'im' in words and len(words[words.index('im') + 1:]) <= 3 and len(words[words.index('im') + 1:]) > 0:
                return await message.channel.send('Hi, ' + ' '.join(words[words.index('im') + 1:]) + ' i\'m <@884378283268014091>')
            if 'i' in words and 'am' in words:
                if words[words.index('i') + 1] == 'am' and len(words[words.index('am') + 1:]) <= 3 and len(words[words.index('am') + 1:]) > 0:
                    return await message.channel.send('Hi, ' + ' '.join(words[words.index('am') + 1:]) + ' i\'m <@884378283268014091>')

            ligmas = [
                ['ligma', 'Ligma balls'],
                ['sugma', 'Sugma balls'],
                ['sucma', 'Sucma balls'],
                ['bofa', 'Bofa deeze nuts in your mouth'],
                ['eatma', 'Eatma balls'],
                ['fugma', 'Fugma balls'],
                ['kisma', 'Kisma balls'],
                ['chokonma', 'Chokonma balls'],
                ['fondalma', 'Fondalma balls'],
                ['stigma', 'I am going to Stigma dick in your ass'],
                ['tugunma', 'Tugunma balls'],
                ['slobonma', 'Slobonma balls'],
                ['cupma', 'Cupma balls'],
                ['nibelma', 'Nibelma balls'],
                ['tipima', 'Tipima dick'],
                ['jergma', 'Jergma dick'],
                ['bofadese', 'Bofadese nuts'],
                ['bophides', 'Bophides nuts'],
                ['dragondese', 'Dragondese nuts across your face'],
                ['sugondese', 'Sugondese nuts'],
                ['rubondese', 'Rubondese nuts'],
                ['imagine dragon', 'Imagine Dragon my balls across your face'],
                ['dragon', 'Dragon my nuts across your face'],
            ]
            for ligma in ligmas:
                if ligma[0] in words:
                    return await message.channel.send(ligma[1])

            if (
                message.content.lower().startswith('whats') or
                message.content.lower().startswith('what\'s') or
                message.content.lower().startswith('what is')
            ):
                words = message.content.lower().replace('?', '').replace('\'', '').split(' ')
                i = 0
                for word in words:
                    if word not in ['what', 'is', 'whats', 'the', 'are', 'your', 'youre', 'are', 'this', 'my']:
                        break
                    i += 1
                
                phrase = words[i:]
                if len(phrase) > 0:
                    return await message.channel.send(' '.join(phrase) + ' my balls')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if not payload.member.bot and payload.emoji.name == 'craigmoment': # and self.bot.random.randint(1, 10) == 7:
            await message.add_reaction(payload.emoji)


async def setup(bot):
    await bot.add_cog(FunCog(bot))