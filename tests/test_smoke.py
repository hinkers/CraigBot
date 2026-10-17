import importlib
from pathlib import Path

import pytest

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
