import json
import os

from discord.ext import commands


class TagCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        if message.content.startswith('!'):
            parts = message.content.split(' ', 1)
            tag_name = parts[0][1:]

            async with self.bot.session as session:
                statement = select(Tag).where(Tag.guild_id == ctx.guild.id, Tag.name == tag_name)
                result = await session.execute(statement)
                tag = result.scalar()

                if tag:
                    await message.channel.send(tag.message)

    @commands.hybrid_group(invoke_without_command=True)
    async def tag(self, ctx, *, name: str):
        async with self.bot.session as session:
            statement = select(Tag).where(Tag.guild_id == ctx.guild.id, Tag.name == name)
            result = await session.execute(statement)
            tag = result.scalar()

            if tag:
                await ctx.send(tag.message)
            else:
                await ctx.send('Tag not found.')

    @tag.command(name='add')
    @commands.has_permissions(manage_messages=True)
    async def tag_add(self, ctx, name: str, *, content: str):
        if name in self.tags:
            await ctx.send('Tag already exists.')
        else:
            self.tags[name] = content
            self.save_tags()
            await ctx.send(f'Tag `{name}` added.')

    @tag.command(name='delete')
    @commands.has_permissions(manage_messages=True)
    async def tag_delete(self, ctx, *, name: str):
        if name in self.tags:
            del self.tags[name]
            self.save_tags()
            await ctx.send(f'Tag `{name}` deleted.')
        else:
            await ctx.send('Tag not found.')

    @tag.command(name='list')
    async def tag_list(self, ctx):
        if self.tags:
            keys = [f'- {k}' for k in self.tags.keys()]
            await ctx.send('```All tags:\n' + '\n'.join(keys) + '```')
        else:
            await ctx.send('No tags available.')


async def setup(bot):
    await bot.add_cog(TagCog(bot))

