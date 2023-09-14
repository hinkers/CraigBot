import json
import os

from discord.ext import commands


class TagsCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.tag_file = "data/tags.json"
        if os.path.exists(self.tag_file):
            with open(self.tag_file, 'r') as f:
                self.tags = json.load(f)
        else:
            self.tags = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        parts = message.content.split(' ', 1)
        if parts[0].startswith('!'):
            tag_name = parts[0][1:]
            tag_content = self.tags.get(tag_name)
            if tag_content:
                await message.channel.send(tag_content)

    def save_tags(self):
        with open(self.tag_file, 'w') as f:
            json.dump(self.tags, f)
    
    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, *, name: str):
        tag = self.tags.get(name)
        if tag:
            await ctx.send(tag)
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
    await bot.add_cog(TagsCog(bot))

