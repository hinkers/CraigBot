import asyncio
import importlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import discord
import pytest
from discord.ext import commands

REPO = Path(__file__).resolve().parent.parent
COG_MODULES = sorted(f'cogs.{path.stem}' for path in (REPO / 'cogs').glob('*.py'))
MODULES = [
    'app',
    'craig',
    'quotes',
    'audio.audio',
    'audio.converter',
    'audio.player',
    'audio.tasks',
    'audio.ytdl_source',
    'database.database',
    'database.audio',
    'database.tag',
    'utils.embedded_messages',
    'utils.logging',
    *COG_MODULES,
]


@pytest.mark.parametrize('name', MODULES)
def test_module_imports(name):
    importlib.import_module(name)


@pytest.mark.parametrize('name', COG_MODULES)
async def test_cog_setup_registers_cog(name):
    module = importlib.import_module(name)
    bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())

    with patch('cogs.audio.AudioCog.initialize_tasks', new_callable=AsyncMock):
        await module.setup(bot)
        await asyncio.sleep(0)  # let any start-up task created in cog_load run

    assert len(bot.cogs) == 1
