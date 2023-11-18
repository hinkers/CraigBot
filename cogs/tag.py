import discord
from discord.ext import commands
from sqlalchemy import select

from database.tag import Tag


class TagCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if message.content.startswith('!'):
            parts = message.content.split(' ', 1)
            tag_name = parts[0][1:]

            async with self.bot.session as session:
                statement = select(Tag).where(Tag.guild_id == message.guild.id, Tag.name == tag_name)
                result = await session.execute(statement)
                tag = result.scalar()

                if tag:
                    await message.channel.send(tag.message)

    @commands.hybrid_group(invoke_without_command=True)
    async def tag(self, ctx, *, name: str):
        await ctx.send('\n'.join([
            '```Commands:',
            '   - tag add <name> <content>',
            '   - tag delete <name> <content>',
            '   - tag list',
            '   - <name>',
            '```'
        ]))

    @tag.command(name='add')
    @commands.has_permissions(manage_messages=True)
    async def tag_add(self, ctx, name: str, *, content: str):
        async with self.bot.session as session:
            statement = select(Tag).where(Tag.guild_id == ctx.guild.id, Tag.name == name)
            result = await session.execute(statement)
            tag = result.scalar()

            if tag:
                await ctx.send('Tag already exists.')
            else:
                tag = Tag(
                    guild_id=ctx.guild.id,
                    user_id=ctx.author.id,
                    name=name,
                    message=content
                )
                session.add(tag)
                await session.commit()
                await ctx.send(f'Tag `{name}` added.')

    @tag.command(name='delete')
    @commands.has_permissions(manage_messages=True)
    async def tag_delete(self, ctx, *, name: str):
        async with self.bot.session as session:
            statement = select(Tag).where(Tag.guild_id == ctx.guild.id, Tag.name == name)
            result = await session.execute(statement)
            tag = result.scalar()

            if tag:
                await session.delete(tag)
                await session.commit()
                await ctx.send(f'Tag `{name}` deleted.')
            else:
                await ctx.send('Tag not found.')

    @tag.command(name='list')
    async def tag_list(self, ctx):
        async with self.bot.session as session:
            statement = select(Tag).where(Tag.guild_id == ctx.guild.id)
            result = await session.execute(statement)
            tags = result.scalars()

            if tags:
                descriptions = [f'- {t.name}' for t in tags.all()]
                await ctx.send('```All tags:\n' + '\n'.join(descriptions) + '```')
            else:
                await ctx.send('No tags available.')

    @commands.command()
    @commands.dm_only()
    @commands.is_owner()
    async def ensure_default_tags(self, ctx: commands.Context, guild: discord.Guild) -> None:
        tag_definitions = [
            ['rules', 'https://cdn.discordapp.com/attachments/752510366340087849/908592891851595816/THE_RULES.jpg?ex=65697292&is=6556fd92&hm=bea2bdd2bc3725fa120a30781baee66d4009a0a5ad62c62f0ea083dd92a33d64&'],
            ['lettuce', 'https://media.discordapp.net/attachments/752510366340087849/881882297387855962/image0.png?ex=65648f64&is=65521a64&hm=df52843527704a26ba375b7f1c447ae338b8930176b6cbe268b6079edda37cc7&=']
        ]

        async with self.bot.session as session:
            for tag_definition in tag_definitions:
                statement = select(Tag).where(Tag.guild_id == guild.id, Tag.name == tag_definition[0])
                result = await session.execute(statement)
                tag = result.scalar()

                if not tag:
                    tag = Tag(
                        guild_id=guild.id,
                        user_id=ctx.author.id,
                        name=tag_definition[0],
                        message=tag_definition[1]
                    )
                    session.add(tag)
                    await session.commit()
                    await ctx.send(f'Tag `{tag_definition[0]}` added.')


async def setup(bot):
    await bot.add_cog(TagCog(bot))

