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

    async def load_extension(self, *names):
        print('Loading cogs:')
        loaded = 0
        for name in names:
            try:
                await super().load_extension(name)
                loaded += 1
                print(f'└──►Loaded: `{name}`')
            except Exception:
                print(f'└──►Failed: `{name}`')
        print(f'Loaded {loaded}/{len(names)} cogs.')


intents = discord.Intents.default()
intents.message_content = True
client = CraigBot(command_prefix='!', intents=intents)


@client.event
async def on_ready():
    await client.load_extension("cogs.admin", "cogs.audio", "cogs.fun", "cogs.poe")
    print(f'\nLogged in as {client.user} (ID: {client.user.id})')
    print('──────')


client.run(os.getenv('BOT_TOKEN'))
