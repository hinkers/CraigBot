import glob
import os
from random import SystemRandom
import traceback

import discord
from discord.ext import commands

from audio.player import AudioPlayer


class CraigBot(commands.Bot):
    def __init__(self, debug, *, command_prefix, intents: discord.Intents):
        super().__init__(command_prefix, intents=intents)
        self.audioplayers = dict()
        self.random = SystemRandom()
        self.coggers = []
        self.debug = debug
    
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
        errors = []
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
            except Exception as e:
                print(f'└──►Failed: `{name}`')
                errors.append(e)
        print(f'Loaded {loaded}/{len(all_files)} cogs.')

        if len(errors) and self.debug:
            print('\nCog errors:')
            for error in errors:
                print(error, '')
            print('')
    
    async def send_owner(self, message):
        app_info = await self.application_info()
        await app_info.owner.send(message)

    async def setup_hook(self):
        if os.path.isfile('last_error.txt'):
            with open('last_error.txt', 'r') as f:
                error = f.read().replace('```', '`\``')
            await self.send_owner(f'```{error}```')
            os.remove('last_error.txt')
        await self.load_extensions()

    async def on_error(self, event, *args, **kwargs):
        error = '\n'.join([
            f'Event: {event}',
            f'Args: {args}',
            f'Kwargs: {kwargs}',
            ' ----- ',
            traceback.format_exc()
        ])
        await self.send_owner(f'```{error}```')

        super().on_error(self, event, args, kwargs)