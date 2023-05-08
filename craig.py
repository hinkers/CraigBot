import glob
import math
import os
from random import SystemRandom

import discord
from discord.ext import commands
from dotenv import load_dotenv

from audio.player import AudioPlayer

if os.getenv('craig_debug') == 'true':
    load_dotenv('dev.env')
else:
    load_dotenv('prod.env')


class CraigBot(commands.Bot):
    def __init__(self, *, command_prefix, intents: discord.Intents):
        super().__init__(command_prefix, intents=intents)
        self.audioplayers = dict()
        self.random = SystemRandom()
        self.coggers = []
    
    def get_audioplayer(self, voice_client):
        try:
            return self.audioplayers[voice_client.channel.id]
        except KeyError:
            self.audioplayers[voice_client.channel.id] = AudioPlayer(voice_client)
            return self.audioplayers[voice_client.channel.id]
    
    def destroy_audioplayer(self, channel):
        try:
            del self.audioplayers[channel.id]
        except KeyError:
            pass

    async def load_extensions(self):
        loaded = 0
        all_files = glob.glob(os.path.join('cogs', '*.py'))
        all_files.sort()
        print(f'Found {len(all_files)} cogs:')
        for file in all_files:
            name = file.replace('/', '.')[:-3]
            try:
                await self.load_extension(name)
                self.coggers.append((name, list(self.cogs.values())[-1].qualified_name))
                loaded += 1
                print(f'└──►Loaded: `{name}`')
            except Exception:
                print(f'└──►Failed: `{name}`')
        print(f'Loaded {loaded}/{len(all_files)} cogs.')
    
    async def setup_hook(self):
        await self.load_extensions()


intents = discord.Intents.default()
intents.message_content = True
client = CraigBot(command_prefix='!', intents=intents)


@client.event
async def on_ready():
    id_str = f' Logged in with ID: {client.user.id} '
    l = (len(id_str) - len(client.user.name)) / 2
    print('\n╭' + ('─' * math.floor(l)) + client.user.name + ('─' * math.ceil(l)) + '╮')
    print(f'│{id_str}│')
    print('╰' + ('─' * len(id_str)) + '╯')


client.run(os.getenv('BOT_TOKEN'))
