# Tests, systemd Service & CI/CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give CraigBot a pytest suite, run it as systemd services instead of `screen` + `run.sh`, and deploy automatically from GitHub Actions when tests pass on `Main`.

**Architecture:** Small testability refactors (configurable DB URL, sessionmakers created on first use, `cog_load` instead of `bot.loop` in `__init__`) let tests import everything without side effects. Tests run against a real Postgres (Docker locally, a service container in CI) inside a per-test transaction that is rolled back. A `deploy/` folder holds two systemd units, a one-time install script and `deploy.sh`, which CI runs over SSH through a forced-command deploy key.

**Tech Stack:** Python 3.12, discord.py 2.6, SQLAlchemy 2.0 (asyncpg / psycopg2), Celery + Redis, pytest 9 + pytest-asyncio 1.4, ruff, GitHub Actions, systemd on Ubuntu 24.04.

**Spec:** `docs/superpowers/specs/2026-10-17-tests-service-cicd-design.md` (read the "Amendments from planning" section; where it disagrees with earlier text, the amendment wins).

## Global Constraints

- Python **3.12** everywhere (server runs 3.12.3; CI uses `python-version: '3.12'`).
- Production behaviour unchanged by refactors: DB defaults to `localhost:5432` built from `DB_USERNAME` / `DB_PASSWORD` / `DB_DATABASE_NAME`; Redis defaults to `redis://localhost:6379` with db `0`/`1` (or `2`/`3` when `craig_debug=true`).
- The server installs only `requirements.txt`. Dev tools go in `requirements-dev.txt` with pins `pytest==9.1.1`, `pytest-asyncio==1.4.0`, `ruff==0.15.1`.
- Ruff runs pyflakes rules only (`select = ["F"]`).
- Tests never contact Discord, YouTube/yt-dlp or Redis/Celery. Patch at the edges.
- Test Postgres: image `postgres:16`, user/password/db `craig_test`. Port **5433** locally (docker compose), 5432 in CI.
- Primary branch is `Main` (capital M). Deploy only on `push` to `Main`.
- GitHub Actions: only `actions/checkout@v5` and `actions/setup-python@v6`. Do not add third-party actions.
- Commands assume the project venv. On this Windows checkout, run Python as `venv/Scripts/python` from Git Bash (for example `venv/Scripts/python -m pytest`). On Linux it is `venv/bin/python`.
- Every commit message ends with a blank line, then `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Pytest pointed at a real database** (for example `DATABASE_URL` left set to production). Test setup drops all tables, so it must refuse any database whose name doesn't contain `test`. Covered by `tests/test_helpers.py` in Task 3.
2. **Playlist links copied from YouTube's share button** (`...&si=...`, `...&index=2`). These must be recognised, not rejected as "Not a valid youtube playlist link". Covered by `tests/test_audio_urls.py` in Task 4.
3. **`!play` with a search that finds nothing.** The user should get "No results found.", not a crashed command with an `IndexError`. Covered by Task 4 (unit) and Task 5 (`test_play_reports_search_with_no_results`).
4. **`!kill` / `!restart`, or a startup error swallowed by `app.py`.** Both exit with status 0, and systemd must still bring the bot back. Covered by `tests/test_deploy_files.py` in Task 7.
5. **A bot that crash-loops after a deploy.** It briefly looks "active" under `Restart=always`, but the deploy must still go red. Covered by `tests/test_deploy_script.py` in Task 7.

---

## File Structure

| Path | Status | Responsibility |
|---|---|---|
| `requirements-dev.txt` | create | Dev/test dependencies on top of `requirements.txt` |
| `pyproject.toml` | create | pytest + ruff config |
| `docker-compose.test.yml` | create | Local throwaway Postgres on port 5433 |
| `.gitattributes` | create | Force LF endings for shell scripts and unit files |
| `database/database.py` | modify | URL building, engines, lazily created shared sessionmakers |
| `craig.py`, `audio/player.py`, `audio/tasks.py` | modify | Use shared sessionmakers instead of import-time engines |
| `cogs/audio.py` | modify | `cog_load` start-up; lint fixes |
| `cogs/tag.py`, `cogs/fun.py`, `audio/audio.py` | modify | Bug fixes the tests surface |
| `tests/__init__.py` | create | Makes `tests.helpers` importable |
| `tests/helpers.py` | create | `FakeBot`, `make_ctx`, `make_message`, `assert_safe_test_database` |
| `tests/conftest.py` | create | DB schema, rolled-back connection, session factory, `db_bot` |
| `tests/test_*.py` | create | Test modules (listed per task) |
| `deploy/craigbot.service`, `deploy/craigbot-celery.service` | create | systemd unit templates |
| `deploy/install-services.sh` | create | One-time install of units + sudoers rule |
| `deploy/deploy.sh` | create | Pull, install, restart, health check |
| `deploy/README.md` | create | Server + GitHub setup and day-to-day operations |
| `.github/workflows/ci.yml` | create | Test job + deploy job |
| `README.md`, `example.env` | modify | Document config, testing, deployment |
| `run.sh` | delete | Replaced by systemd + `deploy.sh` |

---

### Task 1: Dev tooling, lint baseline and import smoke test

**Files:**
- Create: `requirements-dev.txt`, `pyproject.toml`, `docker-compose.test.yml`, `tests/__init__.py`, `tests/test_smoke.py`
- Modify: `audio/tasks.py`, `audio/ytdl_source.py`, `cogs/audio.py`, `cogs/cogs.py`, `cogs/fun.py`, `database/audio.py`, `database/tag.py`, `utils/embedded_messages.py` (lint fixes only)

**Interfaces:**
- Produces: `tests/test_smoke.py` defining `REPO: Path` and `COG_MODULES: list[str]` (`['cogs.admin', 'cogs.audio', 'cogs.cogs', 'cogs.fun', 'cogs.poe', 'cogs.tag']`), which Task 2 extends.
- Produces: `cogs/audio.py` module constant `DELETE_OLD_FILES_TIME` (renamed from `time`).

- [ ] **Step 1: Create the tooling files**

`requirements-dev.txt`:
```text
-r requirements.txt
pytest==9.1.1
pytest-asyncio==1.4.0
ruff==0.15.1
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-ra"

[tool.ruff]
extend-exclude = ["venv"]

[tool.ruff.lint]
select = ["F"]
```

`docker-compose.test.yml`:
```yaml
# Throwaway Postgres for the test suite: docker compose -f docker-compose.test.yml up -d --wait
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: craig_test
      POSTGRES_PASSWORD: craig_test
      POSTGRES_DB: craig_test
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U craig_test"]
      interval: 2s
      timeout: 5s
      retries: 15
```

`tests/__init__.py`: an empty file.

- [ ] **Step 2: Install dev dependencies**

Run: `venv/Scripts/python -m pip install -r requirements-dev.txt`
Expected: installs pytest, pytest-asyncio and ruff without errors.

- [ ] **Step 3: Write the import smoke test**

`tests/test_smoke.py`:
```python
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
```

- [ ] **Step 4: Run the smoke test**

Run: `venv/Scripts/python -m pytest tests/test_smoke.py -v`
Expected: all 19 tests PASS. This test pins current behaviour, so passing straight away is correct. If any import fails, stop and investigate before continuing; it means production startup is already broken.

- [ ] **Step 5: Run ruff to see the baseline**

Run: `venv/Scripts/python -m ruff check .`
Expected: FAIL with these 14 errors:
```text
audio\tasks.py:54:13: F841 Local variable `now_playing` is assigned to but never used
audio\ytdl_source.py:3:8: F401 `asyncio` imported but unused
cogs\audio.py:20:25: F401 `audio.tasks.download` imported but unused
cogs\audio.py:20:35: F401 `audio.tasks.equalise_loudness` imported but unused
cogs\audio.py:24:1: F811 Redefinition of unused `time` from line 5
cogs\audio.py:190:32: F541 f-string without any placeholders
cogs\cogs.py:25:28: F541 / 30:28: F541 / 43:36: F541
cogs\fun.py:1:8: F401 `discord` imported but unused
database\audio.py:2:8: F401 `glob` imported but unused
database\tag.py:3:37: F401 `database.database.get_engine` imported but unused
utils\embedded_messages.py:2:18: F401 `math.floor` / 8:31: F401 `audio.ytdl_source.YTDLSource`
```

- [ ] **Step 6: Apply ruff's safe auto-fixes**

Run: `venv/Scripts/python -m ruff check . --fix`
Expected: fixes the 12 F401/F541 errors; 2 remain (F811, F841).

- [ ] **Step 7: Fix F811 in `cogs/audio.py` by hand**

Delete the `import time` line (line 5). Replace:
```python
time = datetime.time(hour=20, minute=12, tzinfo=pytz.timezone('Australia/Sydney'))
```
with:
```python
DELETE_OLD_FILES_TIME = datetime.time(hour=20, minute=12, tzinfo=pytz.timezone('Australia/Sydney'))
```
and replace `@tasks.loop(time=time)` with `@tasks.loop(time=DELETE_OLD_FILES_TIME)`.

- [ ] **Step 8: Fix F841 in `audio/tasks.py` by hand**

In `download`, replace:
```python
        if song.is_downloaded:
            
            song.date_downloaded = datetime.now()

            statement = select(Guild).where(Guild.now_playing_song_id == song.id)
            result = session.execute(statement)
            now_playing = result.scalar()
            
            # equalise_loudness.delay(song.id, swap_now=now_playing is None)
```
with:
```python
        if song.is_downloaded:
            song.date_downloaded = datetime.now()
```
(The deleted query's result was only used by a commented-out line.) Then delete the now-unused imports `from sqlalchemy import select` and change `from database.audio import Guild, Song` to `from database.audio import Song`.

- [ ] **Step 9: Verify lint and tests are clean**

Run: `venv/Scripts/python -m ruff check . && venv/Scripts/python -m pytest -v`
Expected: `All checks passed!` and 19 tests PASS.

- [ ] **Step 10: Commit**

```bash
git add requirements-dev.txt pyproject.toml docker-compose.test.yml tests/__init__.py tests/test_smoke.py audio cogs database utils
git commit -m "test: add pytest/ruff tooling, import smoke test and lint fixes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Configurable database URL, shared sessionmakers created on first use, `cog_load`

**Files:**
- Modify: `database/database.py` (full rewrite below), `craig.py`, `audio/player.py`, `audio/tasks.py`, `cogs/audio.py`
- Create: `tests/test_database_config.py`
- Modify: `tests/test_smoke.py` (add cog setup test)

**Interfaces:**
- Consumes: `COG_MODULES` from `tests/test_smoke.py` (Task 1).
- Produces (in `database.database`):
  - `with_driver(url: str, async_: bool) -> str`: replaces the scheme with `postgresql+asyncpg` (async) or `postgresql` (sync).
  - `get_database_url(async_: bool = True) -> str`: `DATABASE_URL` if set, otherwise built from `DB_USERNAME`, `DB_PASSWORD`, `DB_HOST` (default `localhost`), `DB_PORT` (default `5432`), `DB_DATABASE_NAME`.
  - `get_engine(async_=True)`: unchanged signature.
  - `get_sessionmaker() -> async_sessionmaker`: shared, cached; builds the engine on first call.
  - `get_sync_sessionmaker() -> sessionmaker`: shared, cached; for Celery.
- Produces: `AudioCog.cog_load()` starts `initialize_tasks()` with `asyncio.create_task`; `AudioCog.__init__` no longer touches `bot.loop`.

- [ ] **Step 1: Write failing config tests**

`tests/test_database_config.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

import database.database as db


def test_with_driver_sets_asyncpg_scheme():
    assert db.with_driver('postgresql://u:p@h:1/d', async_=True) == 'postgresql+asyncpg://u:p@h:1/d'


def test_with_driver_sets_sync_scheme():
    assert db.with_driver('postgresql+asyncpg://u:p@h:1/d', async_=False) == 'postgresql://u:p@h:1/d'


def test_database_url_prefers_database_url(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@h:1/d')

    assert db.get_database_url(async_=True) == 'postgresql+asyncpg://u:p@h:1/d'


def _set_db_credentials(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('DB_HOST', raising=False)
    monkeypatch.delenv('DB_PORT', raising=False)
    monkeypatch.setenv('DB_USERNAME', 'craig')
    monkeypatch.setenv('DB_PASSWORD', 'secret')
    monkeypatch.setenv('DB_DATABASE_NAME', 'craigdb')


def test_database_url_defaults_to_localhost(monkeypatch):
    _set_db_credentials(monkeypatch)

    assert db.get_database_url(async_=False) == 'postgresql://craig:secret@localhost:5432/craigdb'


def test_database_url_uses_host_and_port(monkeypatch):
    _set_db_credentials(monkeypatch)
    monkeypatch.setenv('DB_HOST', 'db.internal')
    monkeypatch.setenv('DB_PORT', '6543')

    assert db.get_database_url(async_=True) == 'postgresql+asyncpg://craig:secret@db.internal:6543/craigdb'


def test_sessionmaker_creates_engine_once(monkeypatch):
    calls = []

    def fake_get_engine(async_=True):
        calls.append(async_)
        return create_async_engine('postgresql+asyncpg://u:p@localhost:1/d')

    monkeypatch.setattr(db, 'get_engine', fake_get_engine)
    monkeypatch.setattr(db, '_async_sessionmaker', None)

    first = db.get_sessionmaker()
    second = db.get_sessionmaker()

    assert first is second
    assert calls == [True]


def test_sync_sessionmaker_creates_engine_once(monkeypatch):
    calls = []

    def fake_get_engine(async_=True):
        calls.append(async_)
        return create_engine('postgresql://u:p@localhost:1/d')

    monkeypatch.setattr(db, 'get_engine', fake_get_engine)
    monkeypatch.setattr(db, '_sync_sessionmaker', None)

    first = db.get_sync_sessionmaker()
    second = db.get_sync_sessionmaker()

    assert first is second
    assert calls == [False]
```

Append to `tests/test_smoke.py`:
```python
import asyncio
from unittest.mock import AsyncMock, patch

import discord
from discord.ext import commands


@pytest.mark.parametrize('name', COG_MODULES)
async def test_cog_setup_registers_cog(name):
    module = importlib.import_module(name)
    bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())

    with patch('cogs.audio.AudioCog.initialize_tasks', new_callable=AsyncMock):
        await module.setup(bot)
        await asyncio.sleep(0)  # let any start-up task created in cog_load run

    assert len(bot.cogs) == 1
```
Move the new imports to the top of the file with the existing imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python -m pytest tests/test_database_config.py tests/test_smoke.py -v`
Expected: the config tests FAIL with `AttributeError: module 'database.database' has no attribute 'with_driver'` (and similar), and `test_cog_setup_registers_cog[cogs.audio]` FAILS with an `AttributeError` about `loop` ("loop attribute cannot be accessed in non-async contexts"). The other cog setup tests PASS.

- [ ] **Step 3: Rewrite `database/database.py`**

```python
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

_async_sessionmaker = None
_sync_sessionmaker = None


def with_driver(url: str, async_: bool) -> str:
    """Return the Postgres URL with its scheme set to the asyncpg (async) or psycopg2 (sync) driver."""
    _, rest = url.split('://', 1)
    scheme = 'postgresql+asyncpg' if async_ else 'postgresql'
    return f'{scheme}://{rest}'


def get_database_url(async_=True) -> str:
    url = os.getenv('DATABASE_URL')
    if url is None:
        username = os.getenv('DB_USERNAME')
        password = os.getenv('DB_PASSWORD')
        database_name = os.getenv('DB_DATABASE_NAME')
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        url = f'postgresql://{username}:{password}@{host}:{port}/{database_name}'
    return with_driver(url, async_)


def get_engine(async_=True):
    if os.getenv('craig_debug') == 'true':
        load_dotenv('dev.env')
    else:
        load_dotenv('prod.env')

    # Create an SQLAlchemy engine
    if async_:
        return create_async_engine(
            get_database_url(async_=True),
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=10,
            max_overflow=20
        )
    return create_engine(
        get_database_url(async_=False),
        pool_pre_ping=True,
        pool_recycle=3600
    )


def get_sessionmaker():
    """Shared async session factory; the engine is created on first use, not at import."""
    global _async_sessionmaker
    if _async_sessionmaker is None:
        _async_sessionmaker = async_sessionmaker(
            autocommit=False, autoflush=False, expire_on_commit=False, bind=get_engine(), class_=AsyncSession
        )
    return _async_sessionmaker


def get_sync_sessionmaker():
    """Shared sync session factory for Celery tasks; the engine is created on first use."""
    global _sync_sessionmaker
    if _sync_sessionmaker is None:
        _sync_sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=get_engine(async_=False))
    return _sync_sessionmaker
```

- [ ] **Step 4: Point `craig.py` at the shared sessionmaker**

Replace:
```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dotenv import load_dotenv
from database.database import Base, get_engine

Session = async_sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=get_engine(), class_=AsyncSession)
```
with:
```python
from sqlalchemy.ext.asyncio import AsyncSession

from dotenv import load_dotenv
from database.database import Base, get_engine, get_sessionmaker
```
and change the `session` property body from `return Session()` to `return get_sessionmaker()()`.

- [ ] **Step 5: Point `audio/player.py` at the shared sessionmaker**

Replace:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, sessionmaker

from audio.tasks import download
from audio.ytdl_source import YTDLSource, ffmpeg_options
from database.audio import Guild, Queue, Song
from database.database import get_engine

Session = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=get_engine(), class_=AsyncSession)
```
with:
```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from audio.tasks import download
from audio.ytdl_source import YTDLSource, ffmpeg_options
from database.audio import Guild, Queue, Song
from database.database import get_sessionmaker
```
and replace both `async with Session() as session:` lines (in `play` and `async_next_song`) with `async with get_sessionmaker()() as session:`.

- [ ] **Step 6: Update `audio/tasks.py`**

Replace the import block and module setup down to the `app = Celery(...)` call:
```python
import os
from datetime import datetime

from celery import Celery
from sqlalchemy.orm import sessionmaker

import audio.converter as converter
from audio.ytdl_source import YTDLSource
from database.audio import Song
from database.database import get_engine

debug = False
if os.getenv('craig_debug') == 'true':
    debug = True

Session = sessionmaker(autocommit=False, autoflush=False, bind=get_engine(async_=False))

broker_id = 0
backend_id = 1
if debug:
    broker_id = 2
    backend_id = 3

app = Celery(
    'audio.tasks',
    broker=f"redis://localhost:6379/{broker_id}",
    backend=f"redis://localhost:6379/{backend_id}"
)
```
with:
```python
import os
from datetime import datetime

from celery import Celery
from dotenv import load_dotenv

import audio.converter as converter
from audio.ytdl_source import YTDLSource
from database.audio import Song
from database.database import get_sync_sessionmaker

debug = False
if os.getenv('craig_debug') == 'true':
    debug = True

load_dotenv('dev.env' if debug else 'prod.env')

broker_id = 0
backend_id = 1
if debug:
    broker_id = 2
    backend_id = 3

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

app = Celery(
    'audio.tasks',
    broker=f"{redis_url}/{broker_id}",
    backend=f"{redis_url}/{backend_id}"
)
```
Then replace both `with Session() as session:` lines with `with get_sync_sessionmaker()() as session:`.

(`load_dotenv` keeps today's behaviour. Before this change, the import-time `get_engine()` call loaded the env file before the Redis URL was built.)

- [ ] **Step 7: Move AudioCog start-up into `cog_load`**

In `cogs/audio.py`, replace:
```python
    def __init__(self, bot):
        self.bot = bot
        self.current_status = None
        bot.loop.create_task(self.initialize_tasks())
```
with:
```python
    def __init__(self, bot):
        self.bot = bot
        self.current_status = None

    async def cog_load(self) -> None:
        # Runs inside the event loop when the cog is added; bot.loop isn't usable before login
        self._init_task = asyncio.create_task(self.initialize_tasks())
```

- [ ] **Step 8: Run tests and lint**

Run: `venv/Scripts/python -m pytest -v && venv/Scripts/python -m ruff check .`
Expected: all tests PASS (19 imports, 6 cog setups, 7 config tests). Ruff: `All checks passed!`

- [ ] **Step 9: Commit**

```bash
git add database/database.py craig.py audio/player.py audio/tasks.py cogs/audio.py tests/test_database_config.py tests/test_smoke.py
git commit -m "refactor: configurable DB/Redis URLs and lazily created sessionmakers

Importing modules no longer builds engines, DATABASE_URL/DB_HOST/DB_PORT/REDIS_URL
override the localhost defaults, and AudioCog starts its tasks in cog_load.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Database test harness, production-DB guard and model tests

**Files:**
- Create: `tests/helpers.py`, `tests/conftest.py`, `tests/test_helpers.py`, `tests/test_database_models.py`

**Interfaces:**
- Consumes: `database.database.Base`, `with_driver` (Task 2).
- Produces (in `tests.helpers`):
  - `FakeBot(session_factory=None)`, with attributes `random` (a `MagicMock`), `debug=True`, `user`, and a `session` property that returns `session_factory()` (or raises `RuntimeError` if there is none).
  - `make_ctx(*, guild_id=1, guild_name='Test Guild', author_id=10, author_name='tester') -> MagicMock`, with `send`, `reply` and `typing` as `AsyncMock`.
  - `make_message(content, *, guild_id=1, author_bot=False, in_guild=True) -> MagicMock`, with `channel.send` and `add_reaction` as `AsyncMock`.
  - `assert_safe_test_database(url: str) -> None`, which raises `RuntimeError('Refusing ...')` unless the database name contains `test`.
- Produces (fixtures in `tests/conftest.py`): `database_schema` (session scope), `db_connection`, `session_factory` (a callable returning a new `AsyncSession` whose commits only release a savepoint), `db_session`, `db_bot` (a `FakeBot` wired to `session_factory`).

- [ ] **Step 1: Write the failing guard test**

`tests/test_helpers.py`:
```python
import pytest

from tests.helpers import assert_safe_test_database


def test_guard_accepts_test_database():
    assert_safe_test_database('postgresql://u:p@localhost:5433/craig_test')


@pytest.mark.parametrize('url', [
    'postgresql://u:p@localhost:5432/craigbot',
    'postgresql://u:p@localhost:5432/',
])
def test_guard_refuses_other_databases(url):
    with pytest.raises(RuntimeError, match='Refusing'):
        assert_safe_test_database(url)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `venv/Scripts/python -m pytest tests/test_helpers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.helpers'`.

- [ ] **Step 3: Write `tests/helpers.py`**

```python
"""Test doubles shared by the cog tests, plus the guard that protects real databases."""
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.engine import make_url


class FakeBot:
    """Stands in for CraigBot: exposes `session`, `random` and `debug` like the real bot."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory
        self.random = MagicMock()
        self.debug = True
        self.user = MagicMock(name='bot_user')

    @property
    def session(self):
        if self._session_factory is None:
            raise RuntimeError('FakeBot was created without a database session factory')
        return self._session_factory()


def make_ctx(*, guild_id=1, guild_name='Test Guild', author_id=10, author_name='tester'):
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.reply = AsyncMock()
    ctx.typing = AsyncMock()
    ctx.guild.id = guild_id
    ctx.guild.name = guild_name
    ctx.author.id = author_id
    ctx.author.name = author_name
    return ctx


def make_message(content, *, guild_id=1, author_bot=False, in_guild=True):
    message = MagicMock()
    message.content = content
    message.author.bot = author_bot
    message.guild = MagicMock(id=guild_id) if in_guild else None
    message.channel.send = AsyncMock()
    message.add_reaction = AsyncMock()
    return message


def assert_safe_test_database(url: str) -> None:
    """Test setup drops every table, so refuse any database not named like a test database."""
    database = make_url(url).database or ''
    if 'test' not in database:
        raise RuntimeError(f'Refusing to use database {database!r} for tests: its name must contain "test".')
```

- [ ] **Step 4: Run the guard test**

Run: `venv/Scripts/python -m pytest tests/test_helpers.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Write `tests/conftest.py`**

```python
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import database.audio  # noqa: F401  (registers the audio models on Base.metadata)
import database.tag  # noqa: F401  (registers the tag model on Base.metadata)
from database.database import Base, with_driver
from tests.helpers import FakeBot, assert_safe_test_database

LOCAL_TEST_DATABASE_URL = 'postgresql://craig_test:craig_test@localhost:5433/craig_test'


def _test_database_url() -> str:
    return os.getenv('DATABASE_URL', LOCAL_TEST_DATABASE_URL)


@pytest.fixture(scope='session')
def database_schema():
    """Create a fresh schema once per run. Locally, skip DB tests if Postgres is down; in CI, fail."""
    url = _test_database_url()
    assert_safe_test_database(url)
    engine = create_engine(with_driver(url, async_=False), poolclass=NullPool)
    try:
        with engine.begin() as connection:
            Base.metadata.drop_all(connection)
            Base.metadata.create_all(connection)
    except OperationalError as error:
        message = (
            f'Postgres not reachable at {url} ({error.orig}). '
            'Start it with: docker compose -f docker-compose.test.yml up -d --wait'
        )
        if os.getenv('CI'):
            pytest.fail(message)
        pytest.skip(message)
    finally:
        engine.dispose()


@pytest.fixture
async def db_connection(database_schema):
    """An async connection inside a transaction that is rolled back after each test."""
    engine = create_async_engine(with_driver(_test_database_url(), async_=True), poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def session_factory(db_connection):
    """Builds sessions configured like the bot's, whose commits only release a savepoint."""
    def factory():
        return AsyncSession(
            bind=db_connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode='create_savepoint',
        )
    return factory


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


@pytest.fixture
def db_bot(session_factory):
    return FakeBot(session_factory)
```

- [ ] **Step 6: Write the model tests**

`tests/test_database_models.py`:
```python
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from database.audio import Favourite, Guild, Queue, Song
from database.tag import Tag


async def test_get_by_reference_finds_existing_song(db_session):
    db_session.add(Song(reference='abc123'))
    await db_session.commit()

    song = await Song.get_by_reference(db_session, 'abc123')

    assert song is not None
    assert song.reference == 'abc123'


async def test_get_by_reference_returns_none_for_unknown(db_session):
    assert await Song.get_by_reference(db_session, 'missing') is None


async def test_get_random_only_picks_playable_songs(db_session):
    db_session.add_all([
        Song(reference='ok', is_downloaded=True, download_error=None),
        Song(reference='ok-empty-error', is_downloaded=True, download_error=''),
        Song(reference='errored', is_downloaded=True, download_error='boom'),
        Song(reference='not-downloaded', is_downloaded=False),
    ])
    await db_session.commit()

    picks = {(await Song.get_random(db_session)).reference for _ in range(20)}

    assert picks <= {'ok', 'ok-empty-error'}


async def test_get_random_returns_none_when_nothing_playable(db_session):
    db_session.add_all([
        Song(reference='errored', is_downloaded=True, download_error='boom'),
        Song(reference='not-downloaded', is_downloaded=False),
    ])
    await db_session.commit()

    assert await Song.get_random(db_session) is None


async def test_ensure_guild_creates_once(db_session):
    first = await Guild.ensure_guild(db_session, 42, 'Guild')
    await db_session.commit()

    second = await Guild.ensure_guild(db_session, 42, 'Guild')
    count = (await db_session.execute(select(func.count()).select_from(Guild))).scalar_one()

    assert first is second
    assert count == 1


async def test_add_song_to_queue_persists_entry(db_session):
    song = Song(reference='abc')
    guild = Guild(id=7, name='Guild')
    db_session.add_all([song, guild])
    await db_session.commit()

    queue = guild.add_song_to_queue(db_session, song)
    queue.order_id = 1
    await db_session.commit()

    result = await db_session.execute(
        select(Queue).where(Queue.guild_id == 7).options(selectinload(Queue.song))
    )
    stored = result.scalar_one()
    assert stored.song.reference == 'abc'
    assert stored.order_id == 1


async def test_favourite_links_to_song(db_session):
    song = Song(reference='fav')
    db_session.add(song)
    await db_session.commit()
    db_session.add(Favourite(user_id=10, name='banger', song_id=song.id))
    await db_session.commit()

    result = await db_session.execute(
        select(Favourite).where(Favourite.name == 'banger').options(selectinload(Favourite.song))
    )

    assert result.scalar_one().song.reference == 'fav'


async def test_tag_round_trip(db_session):
    db_session.add(Tag(guild_id=1, user_id=10, name='rules', message='be nice'))
    await db_session.commit()

    result = await db_session.execute(select(Tag).where(Tag.guild_id == 1, Tag.name == 'rules'))

    assert result.scalar_one().message == 'be nice'
```

- [ ] **Step 7: Check that DB tests skip cleanly with no Postgres**

Run (with Docker's test DB stopped): `venv/Scripts/python -m pytest tests/test_database_models.py -v`
Expected: 8 SKIPPED, with the reason `Postgres not reachable at postgresql://craig_test:craig_test@localhost:5433/craig_test ... Start it with: docker compose ...` shown in the `-ra` summary.

- [ ] **Step 8: Start Postgres and run the model tests**

Run: `docker compose -f docker-compose.test.yml up -d --wait && venv/Scripts/python -m pytest tests/test_database_models.py -v`
Expected: 8 PASS. If `get_random` fails on `session.bind.dialect`, check that the bind is an `AsyncConnection`; it exposes `.dialect` in SQLAlchemy 2.0.

- [ ] **Step 9: Run full suite and lint**

Run: `venv/Scripts/python -m pytest && venv/Scripts/python -m ruff check .`
Expected: all PASS, lint clean.

- [ ] **Step 10: Commit**

```bash
git add tests/helpers.py tests/conftest.py tests/test_helpers.py tests/test_database_models.py
git commit -m "test: add Postgres test harness with rollback isolation and model tests

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Pure unit tests, plus URL-parsing fixes

**Files:**
- Create: `tests/test_audio_urls.py`, `tests/test_song_model.py`, `tests/test_embedded_messages.py`
- Modify: `audio/audio.py` (two one-line fixes)

**Interfaces:**
- Consumes: `audio.audio.extract_youtube_reference_from_url`, `extract_youtube_playlist_reference`, `ensure_youtube_reference`; `database.audio.Song`, `Guild`, `find_yt_dlp_file`; `utils.embedded_messages`.
- Produces: `ensure_youtube_reference` now raises `yt_dlp.utils.DownloadError('No results found.')` on an empty search (Task 5 relies on this). `extract_youtube_playlist_reference` accepts extra query parameters after `list=`.

- [ ] **Step 1: Write URL tests**

`tests/test_audio_urls.py`:
```python
from unittest.mock import patch

import pytest
import yt_dlp

from audio.audio import (ensure_youtube_reference,
                         extract_youtube_playlist_reference,
                         extract_youtube_reference_from_url)

VIDEO_ID = 'dQw4w9WgXcQ'


@pytest.mark.parametrize('url', [
    f'https://www.youtube.com/watch?v={VIDEO_ID}',
    f'https://youtube.com/watch?v={VIDEO_ID}&t=42s',
    f'https://www.youtube.com/watch?list=PL123&v={VIDEO_ID}',
    f'https://www.youtube.com/video/{VIDEO_ID}',
    f'https://youtu.be/{VIDEO_ID}',
    f'https://youtu.be/{VIDEO_ID}?si=shareToken',
])
def test_extracts_video_id(url):
    assert extract_youtube_reference_from_url(url) == VIDEO_ID


@pytest.mark.parametrize('url', ['https://example.com/watch?v=abc', 'never gonna give you up', ''])
def test_non_youtube_returns_none(url):
    assert extract_youtube_reference_from_url(url) is None


@pytest.mark.parametrize('link, expected', [
    ('https://www.youtube.com/playlist?list=PLabc_123-x', 'PLabc_123-x'),
    ('https://www.youtube.com/watch?v=abc&list=PLabc', 'PLabc'),
    ('https://www.youtube.com/playlist?list=PLabc&si=shareToken', 'PLabc'),
    ('https://www.youtube.com/watch?v=abc&list=PLabc&index=2', 'PLabc'),
])
def test_extracts_playlist_id(link, expected):
    assert extract_youtube_playlist_reference(link) == expected


@pytest.mark.parametrize('link', [
    'https://www.youtube.com/watch?v=abc',
    'https://example.com/?list=PLabc',
    'not a link',
])
def test_non_playlist_returns_none(link):
    assert extract_youtube_playlist_reference(link) is None


def test_ensure_reference_uses_url_without_searching():
    with patch('audio.audio.YoutubeSearch') as search:
        assert ensure_youtube_reference(f'https://youtu.be/{VIDEO_ID}') == VIDEO_ID
    search.assert_not_called()


def test_ensure_reference_searches_for_plain_text():
    with patch('audio.audio.YoutubeSearch') as search:
        search.return_value.to_dict.return_value = [{'id': 'found123'}]
        assert ensure_youtube_reference('some song') == 'found123'
    search.assert_called_once_with('some song', max_results=1)


def test_ensure_reference_raises_when_search_finds_nothing():
    with patch('audio.audio.YoutubeSearch') as search:
        search.return_value.to_dict.return_value = []
        with pytest.raises(yt_dlp.utils.DownloadError, match='No results found.'):
            ensure_youtube_reference('zzzz no such song')
```

- [ ] **Step 2: Run to verify the bug tests fail**

Run: `venv/Scripts/python -m pytest tests/test_audio_urls.py -v`
Expected: these 3 FAIL and everything else passes:
- `test_extracts_playlist_id[...si=shareToken...]` and `[...index=2...]` return `None`.
- `test_ensure_reference_raises_when_search_finds_nothing` raises `IndexError`.

- [ ] **Step 3: Fix `audio/audio.py`**

In `ensure_youtube_reference`, replace:
```python
            yt_dlp.utils.DownloadError('No results found.')
```
with:
```python
            raise yt_dlp.utils.DownloadError('No results found.')
```
In `extract_youtube_playlist_reference`, replace:
```python
    playlist_pattern = r'^(?:https?:\/\/)?(?:www\.)?youtube\.com.*?\?.*?list=([\w-]+)$'
```
with:
```python
    playlist_pattern = r'^(?:https?:\/\/)?(?:www\.)?youtube\.com.*?\?.*?list=([\w-]+)'
```

- [ ] **Step 4: Run URL tests**

Run: `venv/Scripts/python -m pytest tests/test_audio_urls.py -v`
Expected: all PASS.

- [ ] **Step 5: Write Song/Guild model unit tests (no DB)**

`tests/test_song_model.py`:
```python
import os

from database.audio import Guild, Song, find_yt_dlp_file

LINK = 'https://www.youtube.com/watch?v=abc123'


def make_song(**overrides):
    fields = dict(reference='abc123', filename='youtube-abc123', extension='mp3')
    fields.update(overrides)
    return Song(**fields)


def test_link():
    assert make_song().link == LINK


def test_full_filename():
    assert make_song().full_filename == os.path.join('data', 'audio_cache', 'youtube-abc123.mp3')


def test_full_normalized_filename():
    assert make_song().full_normalized_filename == os.path.join('data', 'audio_cache', 'youtube-abc123_normalized.mp3')


def test_str_without_title_is_link():
    assert str(make_song()) == LINK


def test_str_with_title():
    assert str(make_song(title='Song')) == f'[Song]\n{LINK}'


def test_info():
    song = make_song(title='Song', channel='Chan', duration=215, view_count=10, like_count=2, thumbnail='http://img')

    assert song.info == dict(
        title='Song',
        webpage_url=LINK,
        thumbnail='http://img',
        channel='Chan',
        duration_string='215',
        duration=215,
        view_count=10,
        like_count=2,
    )


def test_guild_is_playing():
    assert Guild(id=1, now_playing_song_id=None).is_playing is False
    assert Guild(id=1, now_playing_song_id=5).is_playing is True


def test_find_prefers_finished_file(tmp_path):
    base = tmp_path / 'youtube-abc'
    (tmp_path / 'youtube-abc.webm.part').touch()
    (tmp_path / 'youtube-abc.m4a').touch()

    assert find_yt_dlp_file(str(base)) == f'{base}.m4a'


def test_find_falls_back_to_partial_download(tmp_path):
    base = tmp_path / 'youtube-abc'
    (tmp_path / 'youtube-abc.mp3.part').touch()

    assert find_yt_dlp_file(str(base)) == f'{base}.mp3.part'


def test_find_returns_none_when_nothing_downloaded(tmp_path):
    assert find_yt_dlp_file(str(tmp_path / 'youtube-abc')) is None


def test_delete_files_removes_audio_and_resets_flags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / 'data' / 'audio_cache'
    cache.mkdir(parents=True)
    (cache / 'youtube-abc123.mp3').touch()
    (cache / 'youtube-abc123_normalized.mp3').touch()
    song = make_song(is_downloaded=True, is_normalized=True)

    song.delete_files()

    assert list(cache.iterdir()) == []
    assert song.is_downloaded is False
    assert song.is_normalized is False


def test_delete_files_tolerates_missing_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    song = make_song(is_downloaded=True)

    song.delete_files()

    assert song.is_downloaded is False
```

- [ ] **Step 6: Write embed tests**

`tests/test_embedded_messages.py`:
```python
import pytest

from database.audio import Song
from utils import embedded_messages
from utils.embedded_messages import human_numbers


@pytest.mark.parametrize('number, expected', [
    (None, 0),
    (0, '0'),
    (999, '999'),
    (1500, '1K'),
    (2_500_000, '2M'),
    (3_000_000_000, '3B'),
])
def test_human_numbers(number, expected):
    assert human_numbers(number) == expected


def test_now_playing_embed():
    song = Song(
        reference='abc123', title='Song', channel='Chan', view_count=1500,
        like_count=20, duration=215, thumbnail='https://img.example/abc.jpg',
    )

    embed = embedded_messages.now_playing(song)

    assert embed.title == 'Song'
    assert embed.url == song.link
    assert embed.author.name == 'Now Playing'
    assert [(f.name, f.value) for f in embed.fields] == [
        ('Channel', 'Chan'), ('Views', '1K'), ('Likes', '20'), ('Duration', '215'),
    ]
    assert embed.footer.text


def test_queue_embed_numbers_songs():
    playing = Song(reference='now', title='Now')
    upcoming = [Song(reference='next1'), Song(reference='next2', title='Two')]

    embed = embedded_messages.queue(playing, upcoming)

    assert embed.description.splitlines() == [
        '**1) [Now]',
        'https://www.youtube.com/watch?v=now**',
        '2) https://www.youtube.com/watch?v=next1',
        '3) [Two]',
        'https://www.youtube.com/watch?v=next2',
    ]


def test_magic_8_ball_attaches_image():
    result = embedded_messages.magic_8_ball('tester', 'Will it work?', 'Yes')
    try:
        assert result['file'].filename == '8ball.png'
        embed = result['embed']
        assert [(f.name, f.value) for f in embed.fields] == [('tester asks', 'Will it work?'), ('Answer', 'Yes')]
        assert embed.thumbnail.url == 'attachment://8ball.png'
    finally:
        result['file'].close()
```

- [ ] **Step 7: Run the new unit tests**

Run: `venv/Scripts/python -m pytest tests/test_song_model.py tests/test_embedded_messages.py -v`
Expected: all PASS. These pin existing behaviour. If one fails, check the assertion against the code before changing any production code; only change code for a real bug, and keep it to one line.

- [ ] **Step 8: Full suite and lint**

Run: `venv/Scripts/python -m pytest && venv/Scripts/python -m ruff check .`
Expected: all PASS, lint clean.

- [ ] **Step 9: Commit**

```bash
git add audio/audio.py tests/test_audio_urls.py tests/test_song_model.py tests/test_embedded_messages.py
git commit -m "test: unit tests for URL parsing, Song model and embeds

Fixes: searches with no results now raise DownloadError instead of IndexError,
and playlist links with extra params (&si=, &index=) are recognised.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Tag and Audio cog tests (database-backed)

**Files:**
- Create: `tests/test_tag_cog.py`, `tests/test_audio_cog.py`
- Modify: `cogs/tag.py` (fix the empty-list message)

**Interfaces:**
- Consumes: fixtures `db_bot`, `session_factory` (Task 3); `tests.helpers.FakeBot`, `make_ctx`, `make_message` (Task 3); `ensure_youtube_reference` raising on no results (Task 4); `AudioCog` having no `bot.loop` use in `__init__` (Task 2).
- Commands are called through `cog.<command>.callback(cog, ctx, ...)`. This skips Discord's permission checks and `before_invoke` voice hooks on purpose. `audio.player.play` is always patched, because it would start voice playback.

- [ ] **Step 1: Write tag cog tests**

`tests/test_tag_cog.py`:
```python
import pytest
from sqlalchemy import select

from cogs.tag import TagCog
from database.tag import Tag
from tests.helpers import FakeBot, make_ctx, make_message


@pytest.fixture
def cog(db_bot):
    return TagCog(db_bot)


async def add_tag(session_factory, name='rules', message='be nice', guild_id=1):
    async with session_factory() as session:
        session.add(Tag(guild_id=guild_id, user_id=10, name=name, message=message))
        await session.commit()


async def stored_tags(session_factory, guild_id=1):
    async with session_factory() as session:
        result = await session.execute(select(Tag).where(Tag.guild_id == guild_id))
        return {tag.name: tag.message for tag in result.scalars()}


async def test_tag_add_creates_tag(cog, session_factory):
    ctx = make_ctx()

    await cog.tag_add.callback(cog, ctx, 'rules', content='be nice')

    ctx.send.assert_awaited_once_with('Tag `rules` added.')
    assert await stored_tags(session_factory) == {'rules': 'be nice'}


async def test_tag_add_rejects_duplicate(cog, session_factory):
    await add_tag(session_factory)
    ctx = make_ctx()

    await cog.tag_add.callback(cog, ctx, 'rules', content='something else')

    ctx.send.assert_awaited_once_with('Tag already exists.')
    assert await stored_tags(session_factory) == {'rules': 'be nice'}


async def test_tags_are_per_guild(cog, session_factory):
    await add_tag(session_factory, guild_id=2)
    ctx = make_ctx(guild_id=1)

    await cog.tag_add.callback(cog, ctx, 'rules', content='guild one rules')

    ctx.send.assert_awaited_once_with('Tag `rules` added.')


async def test_tag_delete_removes_tag(cog, session_factory):
    await add_tag(session_factory)
    ctx = make_ctx()

    await cog.tag_delete.callback(cog, ctx, name='rules')

    ctx.send.assert_awaited_once_with('Tag `rules` deleted.')
    assert await stored_tags(session_factory) == {}


async def test_tag_delete_missing_tag(cog):
    ctx = make_ctx()

    await cog.tag_delete.callback(cog, ctx, name='nope')

    ctx.send.assert_awaited_once_with('Tag not found.')


async def test_tag_list_shows_tags(cog, session_factory):
    await add_tag(session_factory, name='rules')
    await add_tag(session_factory, name='lettuce')
    ctx = make_ctx()

    await cog.tag_list.callback(cog, ctx)

    message = ctx.send.call_args.args[0]
    assert message.startswith('```All tags:\n')
    assert '- rules' in message
    assert '- lettuce' in message


async def test_tag_list_empty_says_so(cog):
    ctx = make_ctx()

    await cog.tag_list.callback(cog, ctx)

    ctx.send.assert_awaited_once_with('No tags available.')


@pytest.mark.parametrize('content', ['!rules', '!rules please'])
async def test_on_message_replies_with_tag(cog, session_factory, content):
    await add_tag(session_factory)
    message = make_message(content)

    await cog.on_message(message)

    message.channel.send.assert_awaited_once_with('be nice')


async def test_on_message_unknown_tag_is_silent(cog):
    message = make_message('!nothing')

    await cog.on_message(message)

    message.channel.send.assert_not_awaited()


@pytest.mark.parametrize('message', [
    make_message('!rules', author_bot=True),
    make_message('!rules', in_guild=False),
])
async def test_on_message_ignores_bots_and_dms(message):
    cog = TagCog(FakeBot())  # no session factory: touching the DB would raise

    await cog.on_message(message)

    message.channel.send.assert_not_awaited()
```

- [ ] **Step 2: Run to verify the empty-list bug test fails**

Run: `docker compose -f docker-compose.test.yml up -d --wait && venv/Scripts/python -m pytest tests/test_tag_cog.py -v`
Expected: `test_tag_list_empty_says_so` FAILS (it sends `'```All tags:\n```'`, because a `ScalarResult` is always truthy). Everything else PASSES.

- [ ] **Step 3: Fix `cogs/tag.py`**

In `tag_list`, replace:
```python
            tags = result.scalars()

            if tags:
                descriptions = [f'- {t.name}' for t in tags.all()]
```
with:
```python
            tags = result.scalars().all()

            if tags:
                descriptions = [f'- {t.name}' for t in tags]
```

- [ ] **Step 4: Run tag tests**

Run: `venv/Scripts/python -m pytest tests/test_tag_cog.py -v`
Expected: all PASS.

- [ ] **Step 5: Write audio cog tests**

`tests/test_audio_cog.py`:
```python
import random
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from cogs.audio import AudioCog
from database.audio import Favourite, Guild, Queue, Song
from tests.helpers import make_ctx


@pytest.fixture
def cog(db_bot):
    return AudioCog(db_bot)


@pytest.fixture
def player_play():
    with patch('audio.player.play', new_callable=AsyncMock) as play:
        yield play


async def queued(session_factory, guild_id=1):
    async with session_factory() as session:
        result = await session.execute(
            select(Queue).where(Queue.guild_id == guild_id).order_by(Queue.order_id).options(selectinload(Queue.song))
        )
        return [(queue.order_id, queue.song.reference) for queue in result.scalars()]


async def add_song(session_factory, **fields):
    async with session_factory() as session:
        song = Song(**fields)
        session.add(song)
        await session.commit()
        return song


async def add_favourite(session_factory, *, user_id, name, reference):
    song = await add_song(session_factory, reference=reference)
    async with session_factory() as session:
        session.add(Favourite(user_id=user_id, name=name, song_id=song.id))
        await session.commit()


async def stored_favourites(session_factory):
    async with session_factory() as session:
        result = await session.execute(select(Favourite).options(selectinload(Favourite.song)))
        return sorted((f.user_id, f.name, f.song.reference) for f in result.scalars())


async def test_play_without_query_asks_for_one(cog, player_play):
    ctx = make_ctx()

    await cog.play.callback(cog, ctx, query=None)

    ctx.send.assert_awaited_once_with('Please provide a YouTube URL or search query.')
    player_play.assert_not_awaited()


async def test_play_queues_new_song_and_starts_player(cog, player_play, session_factory):
    ctx = make_ctx()

    with patch('cogs.audio.ensure_youtube_reference', return_value='abc123'):
        await cog.play.callback(cog, ctx, query='some song')

    ctx.send.assert_awaited_once_with('Added to queue: https://www.youtube.com/watch?v=abc123')
    player_play.assert_awaited_once_with(ctx)
    assert await queued(session_factory) == [(1, 'abc123')]


async def test_play_appends_to_existing_queue(cog, player_play, session_factory):
    with patch('cogs.audio.ensure_youtube_reference', side_effect=['first', 'second']):
        await cog.play.callback(cog, make_ctx(), query='one')
        await cog.play.callback(cog, make_ctx(), query='two')

    assert await queued(session_factory) == [(1, 'first'), (2, 'second')]


async def test_play_reuses_existing_song_row(cog, player_play, session_factory):
    with patch('cogs.audio.ensure_youtube_reference', return_value='abc123'):
        await cog.play.callback(cog, make_ctx(), query='one')
        await cog.play.callback(cog, make_ctx(), query='one again')

    async with session_factory() as session:
        song_count = (await session.execute(select(func.count()).select_from(Song))).scalar_one()
    assert song_count == 1
    assert await queued(session_factory) == [(1, 'abc123'), (2, 'abc123')]


async def test_play_reports_search_with_no_results(cog, player_play):
    ctx = make_ctx()

    with patch('audio.audio.YoutubeSearch') as search:
        search.return_value.to_dict.return_value = []
        await cog.play.callback(cog, ctx, query='zzzz no such song')

    ctx.send.assert_awaited_once_with('No results found.')
    player_play.assert_not_awaited()


async def test_rplay_with_no_downloaded_songs(cog, player_play):
    ctx = make_ctx()

    await cog.rplay.callback(cog, ctx)

    ctx.send.assert_awaited_once_with('No downloaded songs available in the database.')
    player_play.assert_not_awaited()


async def test_rplay_queues_a_downloaded_song(cog, player_play, session_factory):
    await add_song(session_factory, reference='ready', is_downloaded=True)

    await cog.rplay.callback(cog, make_ctx())

    assert await queued(session_factory) == [(1, 'ready')]


async def test_now_playing_when_idle(cog):
    ctx = make_ctx()

    await cog.now_playing.callback(cog, ctx)

    ctx.send.assert_awaited_once_with('Nothing is currently playing.')


async def test_now_playing_shows_embed(cog, session_factory):
    song = await add_song(session_factory, reference='abc123', title='Banger')
    async with session_factory() as session:
        session.add(Guild(id=1, name='Test Guild', now_playing_song_id=song.id))
        await session.commit()
    ctx = make_ctx()

    await cog.now_playing.callback(cog, ctx)

    assert ctx.send.call_args.kwargs['embed'].title == 'Banger'


async def test_shuffle_renumbers_queue(cog, db_bot, session_factory):
    db_bot.random = random.Random(0)
    async with session_factory() as session:
        songs = [Song(reference=f's{i}') for i in range(5)]
        session.add_all([*songs, Guild(id=1, name='Test Guild')])
        await session.commit()
        for order_id, song in enumerate(songs, start=1):
            session.add(Queue(guild_id=1, song_id=song.id, order_id=order_id))
        await session.commit()
    ctx = make_ctx()

    await cog.shuffle.callback(cog, ctx)

    ctx.send.assert_awaited_once_with("It's probably shuffled now")
    result = await queued(session_factory)
    assert sorted(order for order, _ in result) == [0, 1, 2, 3, 4]
    assert sorted(reference for _, reference in result) == ['s0', 's1', 's2', 's3', 's4']


async def test_favourite_add_creates_favourite(cog, session_factory):
    ctx = make_ctx(author_id=10)

    with patch('cogs.audio.ensure_youtube_reference', return_value='abc123'):
        await cog.favourite_add.callback(cog, ctx, 'https://youtu.be/abc123', name='banger')

    ctx.send.assert_awaited_once_with('Favourite `banger` added.')
    assert await stored_favourites(session_factory) == [(10, 'banger', 'abc123')]


async def test_favourite_add_rejects_duplicate_name(cog, session_factory):
    await add_favourite(session_factory, user_id=10, name='banger', reference='old')
    ctx = make_ctx(author_id=10)

    with patch('cogs.audio.ensure_youtube_reference', return_value='new'):
        await cog.favourite_add.callback(cog, ctx, 'https://youtu.be/new', name='banger')

    ctx.send.assert_awaited_once_with('Favourite name already exists.')
    assert await stored_favourites(session_factory) == [(10, 'banger', 'old')]


async def test_favourite_delete(cog, session_factory):
    await add_favourite(session_factory, user_id=10, name='banger', reference='abc123')
    ctx = make_ctx(author_id=10)

    await cog.favourite_delete.callback(cog, ctx, name='banger')

    ctx.send.assert_awaited_once_with('Favourite `banger` deleted.')
    assert await stored_favourites(session_factory) == []


async def test_favourite_delete_missing(cog):
    ctx = make_ctx(author_id=10)

    await cog.favourite_delete.callback(cog, ctx, name='nope')

    ctx.send.assert_awaited_once_with('Favourite not found.')


async def test_favourite_list_only_shows_own(cog, session_factory):
    await add_favourite(session_factory, user_id=10, name='mine', reference='a')
    await add_favourite(session_factory, user_id=11, name='theirs', reference='b')
    ctx = make_ctx(author_id=10)

    await cog.favourite_list.callback(cog, ctx)

    ctx.send.assert_awaited_once_with('```All your favourites:\n- mine```')


async def test_favourite_list_empty(cog):
    ctx = make_ctx(author_id=10)

    await cog.favourite_list.callback(cog, ctx)

    ctx.send.assert_awaited_once_with('No favourites available.')


async def test_playf_unknown_favourite(cog, player_play):
    ctx = make_ctx(author_id=10)

    await cog.playf.callback(cog, ctx, name='nope')

    ctx.send.assert_awaited_once_with('Favourite not found.')
    player_play.assert_not_awaited()


async def test_playf_queues_favourite(cog, player_play, session_factory):
    await add_favourite(session_factory, user_id=10, name='banger', reference='abc123')

    await cog.playf.callback(cog, make_ctx(author_id=10), name='banger')

    assert await queued(session_factory) == [(1, 'abc123')]
```

- [ ] **Step 6: Run audio cog tests**

Run: `venv/Scripts/python -m pytest tests/test_audio_cog.py -v`
Expected: all PASS. These pin existing behaviour, apart from `test_play_reports_search_with_no_results`, which depends on Task 4's fix. If one fails, read the cog code first. Fix production code only for a real bug that takes a one-line change; anything bigger gets `@pytest.mark.xfail(reason='...', strict=True)` and goes on the list in the final report.

- [ ] **Step 7: Full suite and lint**

Run: `venv/Scripts/python -m pytest && venv/Scripts/python -m ruff check .`
Expected: all PASS, lint clean.

- [ ] **Step 8: Commit**

```bash
git add cogs/tag.py tests/test_tag_cog.py tests/test_audio_cog.py
git commit -m "test: cog tests for tags, playback queueing and favourites

Fixes: 'tag list' now says 'No tags available.' when a guild has no tags.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Fun, Admin and PoE cog tests (no database)

**Files:**
- Create: `tests/test_fun_cog.py`, `tests/test_admin_poe_cogs.py`
- Modify: `cogs/fun.py` (fix an `IndexError` on messages like "am i")

**Interfaces:**
- Consumes: `tests.helpers.FakeBot`, `make_ctx`, `make_message` (Task 3).

- [ ] **Step 1: Write fun cog tests**

`tests/test_fun_cog.py`:
```python
import pytest

from cogs.fun import FunCog
from tests.helpers import FakeBot, make_ctx, make_message

CRAIG = '<@884378283268014091>'


@pytest.fixture
def cog():
    bot = FakeBot()
    bot.random.randint.return_value = 1  # never trigger the random craigmoment reaction
    bot.random.choice.return_value = 'Yes'
    return FunCog(bot)


@pytest.mark.parametrize('content, reply', [
    ('im hungry', f"Hi, hungry i'm {CRAIG}"),
    ("I'm so tired", f"Hi, so tired i'm {CRAIG}"),
    ('I am groot', f"Hi, groot i'm {CRAIG}"),
    ('what is love', 'love my balls'),
    ('ligma', 'Ligma balls'),
])
async def test_on_message_jokes(cog, content, reply):
    message = make_message(content)

    await cog.on_message(message)

    message.channel.send.assert_awaited_once_with(reply)


@pytest.mark.parametrize('content', [
    'am i',
    'is it i',
    'hello there',
    'im',
    'im not going to do that today',
])
async def test_on_message_stays_quiet(cog, content):
    message = make_message(content)

    await cog.on_message(message)

    message.channel.send.assert_not_awaited()
    message.add_reaction.assert_not_awaited()


async def test_on_message_ignores_bots(cog):
    message = make_message('im hungry', author_bot=True)

    await cog.on_message(message)

    message.channel.send.assert_not_awaited()


async def test_eight_ball_requires_question(cog):
    ctx = make_ctx()

    await cog.eight_ball.callback(cog, ctx, question=None)

    ctx.reply.assert_awaited_once_with('You did not ask a valid question that can be correctly read.')


async def test_eight_ball_answers(cog):
    ctx = make_ctx(author_name='tester')

    await cog.eight_ball.callback(cog, ctx, question='Will it work?')

    kwargs = ctx.send.call_args.kwargs
    try:
        assert kwargs['embed'].fields[0].name == 'tester asks'
        assert kwargs['embed'].fields[1].value == 'Yes'
    finally:
        kwargs['file'].close()
```

- [ ] **Step 2: Run to verify the "am i" test fails**

Run: `venv/Scripts/python -m pytest tests/test_fun_cog.py -v`
Expected: `test_on_message_stays_quiet[am i]` FAILS with `IndexError: list index out of range`. Everything else PASSES.

- [ ] **Step 3: Fix `cogs/fun.py`**

Replace:
```python
            if 'i' in words and 'am' in words:
                if words[words.index('i') + 1] == 'am' and len(words[words.index('am') + 1:]) <= 3 and len(words[words.index('am') + 1:]) > 0:
```
with:
```python
            if 'i' in words and 'am' in words:
                after_i = words.index('i') + 1
                if after_i < len(words) and words[after_i] == 'am' and len(words[words.index('am') + 1:]) <= 3 and len(words[words.index('am') + 1:]) > 0:
```

- [ ] **Step 4: Run fun tests**

Run: `venv/Scripts/python -m pytest tests/test_fun_cog.py -v`
Expected: all PASS.

- [ ] **Step 5: Write admin and PoE tests**

`tests/test_admin_poe_cogs.py`:
```python
from unittest.mock import AsyncMock, patch

import pytest

from cogs.admin import AdminCog
from cogs.poe import PoeCog
from tests.helpers import FakeBot, make_ctx

HEADERS = ['Map', 'Card', 'Stack', 'Value', 'Weight']
ROWS = [
    {'Map': 'Dunes', 'Card': 'The Doctor', 'Stack': '8', 'Value': '1000', 'Weight': '1'},
    {'Map': 'Jungle Valley', 'Card': 'Rain of Chaos', 'Stack': '8', 'Value': '1', 'Weight': '100'},
]


async def test_ping_replies_pong():
    cog = AdminCog(FakeBot())
    ctx = make_ctx()

    await cog.ping.callback(cog, ctx)

    ctx.send.assert_awaited_once_with('pong', ephemeral=True)


@pytest.fixture
def poe_cog():
    cog = PoeCog(FakeBot())
    cog.headers = HEADERS
    cog.csv_data = ROWS
    return cog


def test_poe_by_map_matches_partial_name(poe_cog):
    table = poe_cog.poe_by_map('dun')

    assert 'The Doctor' in table
    assert 'Rain of Chaos' not in table


def test_poe_by_card_matches_partial_name(poe_cog):
    table = poe_cog.poe_by_card('rain')

    assert 'Jungle Valley' in table
    assert 'Dunes' not in table


def test_poe_no_match_returns_empty(poe_cog):
    assert poe_cog.poe_by_map('nowhere') == ''
    assert poe_cog.poe_by_card('nothing') == ''


async def test_poe_command_map_search(poe_cog):
    ctx = make_ctx()

    with patch.object(poe_cog, 'poe_get_csv_data', new_callable=AsyncMock):
        await poe_cog.poe.callback(poe_cog, ctx, query='dunes')

    assert ctx.send.call_args.args[0].startswith('Map Search: `dunes`')
    assert ctx.send.call_args.kwargs == {'ephemeral': True}


async def test_poe_command_no_results(poe_cog):
    ctx = make_ctx()

    with patch.object(poe_cog, 'poe_get_csv_data', new_callable=AsyncMock):
        await poe_cog.poe.callback(poe_cog, ctx, query='zzz')

    ctx.send.assert_awaited_once_with('No results found.', ephemeral=True)


async def test_poe_command_when_download_failed():
    cog = PoeCog(FakeBot())
    ctx = make_ctx()

    with patch.object(cog, 'poe_get_csv_data', new_callable=AsyncMock):
        await cog.poe.callback(cog, ctx, query='dunes')

    ctx.send.assert_awaited_once_with('Unable to scam https://divcards.io/')
```

- [ ] **Step 6: Run, then run the full suite and lint**

Run: `venv/Scripts/python -m pytest -v && venv/Scripts/python -m ruff check .`
Expected: all PASS, lint clean.

- [ ] **Step 7: Commit**

```bash
git add cogs/fun.py tests/test_fun_cog.py tests/test_admin_poe_cogs.py
git commit -m "test: cog tests for fun, admin and PoE commands

Fixes: messages like 'am i' no longer raise IndexError in the fun cog listener.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: systemd units, install script and deploy script

**Files:**
- Create: `.gitattributes`, `deploy/craigbot.service`, `deploy/craigbot-celery.service`, `deploy/install-services.sh`, `deploy/deploy.sh`, `tests/test_deploy_files.py`, `tests/test_deploy_script.py`

**Interfaces:**
- Produces: `deploy/deploy.sh`, which takes no arguments (`--pulled` is internal). Exit 0 means both units are active with a stable PID after the settle wait; non-zero means the pull failed, the install failed, or a unit is unhealthy. Task 8's workflow runs it over SSH; `deploy/README.md` (Task 9) documents it.
- Produces: unit templates with `__USER__` / `__APP_DIR__` placeholders, filled in by `sudo deploy/install-services.sh`.
- The sudoers rule allows exactly `/usr/bin/systemctl restart craigbot-celery craigbot`. `deploy.sh` must call exactly `sudo systemctl restart craigbot-celery craigbot`.

- [ ] **Step 1: Write the failing deploy file tests**

`tests/test_deploy_files.py`:
```python
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parent.parent / 'deploy'
UNITS = ['craigbot.service', 'craigbot-celery.service']
RESTART_COMMAND = 'systemctl restart craigbot-celery craigbot'


@pytest.mark.parametrize('unit', UNITS)
def test_unit_restarts_even_after_clean_exit(unit):
    # !kill/!restart and app.py's error handler both exit with status 0
    assert 'Restart=always' in (DEPLOY / unit).read_text().splitlines()


@pytest.mark.parametrize('unit', UNITS)
def test_unit_is_templated(unit):
    text = (DEPLOY / unit).read_text()

    assert '__USER__' in text
    assert '__APP_DIR__' in text


def test_sudoers_rule_matches_deploy_restart_command():
    assert f'sudo {RESTART_COMMAND}' in (DEPLOY / 'deploy.sh').read_text()
    assert f'/usr/bin/{RESTART_COMMAND}' in (DEPLOY / 'install-services.sh').read_text()
```

`tests/test_deploy_script.py`:
```python
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    sys.platform == 'win32', reason='deploy.sh runs on the Linux server; exercised in CI'
)


def write_stub(directory, name, body):
    path = directory / name
    path.write_text('#!/usr/bin/env bash\n' + body)
    path.chmod(0o755)


def run_deploy(tmp_path, *, git_exit=0, pids=('100', '100'), active=True):
    """Run deploy.sh in a fake checkout with git/sudo/systemctl/sleep/journalctl stubbed on PATH."""
    app = tmp_path / 'app'
    (app / 'deploy').mkdir(parents=True)
    shutil.copy(REPO / 'deploy' / 'deploy.sh', app / 'deploy' / 'deploy.sh')
    (app / 'requirements.txt').write_text('')
    venv_bin = app / 'venv' / 'bin'
    venv_bin.mkdir(parents=True)
    write_stub(venv_bin, 'pip', 'echo "pip $*" >> "$CALLS"\n')

    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    write_stub(bin_dir, 'git', f'echo "git $*" >> "$CALLS"\nexit {git_exit}\n')
    write_stub(bin_dir, 'sudo', 'echo "sudo $*" >> "$CALLS"\n')
    write_stub(bin_dir, 'sleep', 'true\n')
    write_stub(bin_dir, 'journalctl', 'echo "journal for $*"\n')
    # The first MainPID read per unit (2 total) returns pids[0]; later reads return pids[1]
    write_stub(bin_dir, 'systemctl', f'''
case "$1" in
  show)
    n=$(( $(cat "$PID_READS" 2>/dev/null || echo 0) + 1 ))
    echo "$n" > "$PID_READS"
    if [ "$n" -le 2 ]; then echo {pids[0]}; else echo {pids[1]}; fi ;;
  is-active) exit {0 if active else 3} ;;
esac
''')

    calls = tmp_path / 'calls.log'
    env = {
        **os.environ,
        'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}',
        'CALLS': str(calls),
        'PID_READS': str(tmp_path / 'pid_reads'),
    }
    result = subprocess.run(
        ['bash', str(app / 'deploy' / 'deploy.sh')],
        env=env, capture_output=True, text=True, cwd=tmp_path,
    )
    recorded = calls.read_text().splitlines() if calls.exists() else []
    return result, recorded


def test_healthy_deploy_pulls_installs_and_restarts(tmp_path):
    result, calls = run_deploy(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert calls == [
        'git pull --ff-only',
        'pip install --quiet --disable-pip-version-check -r requirements.txt',
        'sudo systemctl restart craigbot-celery craigbot',
    ]


def test_failed_pull_stops_before_restarting(tmp_path):
    result, calls = run_deploy(tmp_path, git_exit=1)

    assert result.returncode != 0
    assert not any(call.startswith('sudo') for call in calls)


def test_crash_looping_service_fails_deploy(tmp_path):
    result, _ = run_deploy(tmp_path, pids=('100', '200'))

    assert result.returncode == 1
    assert 'UNHEALTHY' in result.stdout
    assert 'journal for' in result.stdout


def test_inactive_service_fails_deploy(tmp_path):
    result, _ = run_deploy(tmp_path, active=False)

    assert result.returncode == 1


def test_service_without_main_process_fails_deploy(tmp_path):
    result, _ = run_deploy(tmp_path, pids=('0', '0'))

    assert result.returncode == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/Scripts/python -m pytest tests/test_deploy_files.py tests/test_deploy_script.py -v`
Expected: `test_deploy_files.py` FAILS with `FileNotFoundError` for `deploy/...`. `test_deploy_script.py` shows as SKIPPED on Windows; it runs in CI on Linux.

- [ ] **Step 3: Create `.gitattributes`**

```text
*.sh text eol=lf
*.service text eol=lf
```

- [ ] **Step 4: Create `deploy/craigbot.service`**

```ini
[Unit]
Description=CraigBot Discord bot
Wants=network-online.target craigbot-celery.service
After=network-online.target postgresql.service redis-server.service craigbot-celery.service

[Service]
Type=simple
User=__USER__
WorkingDirectory=__APP_DIR__
Environment=PYTHONUNBUFFERED=1
ExecStart=__APP_DIR__/venv/bin/python app.py
# Always restart: !kill/!restart and app.py's error handler both exit with status 0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 5: Create `deploy/craigbot-celery.service`**

```ini
[Unit]
Description=CraigBot Celery worker (audio downloads)
Wants=network-online.target
After=network-online.target postgresql.service redis-server.service

[Service]
Type=simple
User=__USER__
WorkingDirectory=__APP_DIR__
Environment=PYTHONUNBUFFERED=1
# YouTube changes often, so keep yt-dlp current on every start like run.sh's pip-review did (failure is non-fatal)
ExecStartPre=-__APP_DIR__/venv/bin/pip install --quiet --disable-pip-version-check --upgrade yt-dlp
ExecStart=__APP_DIR__/venv/bin/celery -A audio.tasks worker --concurrency=1
Restart=always
RestartSec=5
TimeoutStartSec=180

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 6: Create `deploy/install-services.sh`**

```bash
#!/usr/bin/env bash
# One-time setup: installs the systemd units and the passwordless restart rule used by deploy.sh.
# Usage, from the checkout as the bot's user: sudo deploy/install-services.sh
set -euo pipefail

main() {
    if [[ $EUID -ne 0 || -z "${SUDO_USER:-}" ]]; then
        echo "Run this with sudo as the bot's user: sudo deploy/install-services.sh" >&2
        exit 1
    fi

    local app_dir user
    app_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    user="$SUDO_USER"

    echo "==> Installing systemd units for user $user in $app_dir"
    for unit in craigbot craigbot-celery; do
        sed -e "s|__USER__|$user|g" -e "s|__APP_DIR__|$app_dir|g" \
            "$app_dir/deploy/$unit.service" > "/etc/systemd/system/$unit.service"
    done

    echo "==> Allowing $user to restart the services without a password"
    local sudoers_tmp
    sudoers_tmp="$(mktemp)"
    echo "$user ALL=(root) NOPASSWD: /usr/bin/systemctl restart craigbot-celery craigbot" > "$sudoers_tmp"
    visudo -cf "$sudoers_tmp"
    install -m 0440 "$sudoers_tmp" /etc/sudoers.d/craigbot-deploy
    rm -f "$sudoers_tmp"

    echo "==> Letting $user read the services' logs"
    usermod -aG systemd-journal "$user"

    systemctl daemon-reload
    systemctl enable craigbot-celery craigbot
    echo "Done. Stop the old screen session, then run: sudo systemctl start craigbot-celery craigbot"
}

main "$@"
```

- [ ] **Step 7: Create `deploy/deploy.sh`**

```bash
#!/usr/bin/env bash
# Deploys the latest Main: pull, install pinned deps, restart services, then check they stay up.
# Run by GitHub Actions over SSH (as the deploy key's forced command) or by hand on the server.
set -euo pipefail

UNITS=(craigbot-celery craigbot)

main() {
    local app_dir
    app_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$app_dir"

    if [[ "${1:-}" != "--pulled" ]]; then
        echo "==> Pulling latest code"
        git pull --ff-only
        # Continue with the freshly pulled copy of this script
        exec bash "$app_dir/deploy/deploy.sh" --pulled
    fi

    echo "==> Installing dependencies"
    venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

    echo "==> Restarting services"
    sudo systemctl restart craigbot-celery craigbot

    # With Restart=always a crashing unit flickers back to "active", so also require a stable PID
    echo "==> Checking services stay up"
    sleep 5
    local -A first_pid
    local unit
    for unit in "${UNITS[@]}"; do
        first_pid[$unit]="$(systemctl show -p MainPID --value "$unit")"
    done
    sleep 15

    local failed=0 pid
    for unit in "${UNITS[@]}"; do
        pid="$(systemctl show -p MainPID --value "$unit")"
        if systemctl is-active --quiet "$unit" && [[ "$pid" != "0" && "$pid" == "${first_pid[$unit]}" ]]; then
            echo "    $unit: healthy (pid $pid)"
        else
            echo "    $unit: UNHEALTHY (pid ${first_pid[$unit]} -> $pid)"
            journalctl -u "$unit" -n 50 --no-pager || true
            failed=1
        fi
    done
    return "$failed"
}

main "$@"
```

- [ ] **Step 8: Mark scripts executable in git (needed on the Linux server)**

Run: `git add deploy/deploy.sh deploy/install-services.sh && git update-index --chmod=+x deploy/deploy.sh deploy/install-services.sh`
Expected: `git ls-files -s deploy/*.sh` shows mode `100755` for both.

- [ ] **Step 9: Run tests and a syntax check**

Run: `venv/Scripts/python -m pytest tests/test_deploy_files.py tests/test_deploy_script.py -v && bash -n deploy/deploy.sh && bash -n deploy/install-services.sh`
Expected: 5 PASS in `test_deploy_files.py`; `test_deploy_script.py` SKIPPED on Windows; no syntax errors. If WSL or Linux is available, also run `test_deploy_script.py` there and expect 5 PASS. Otherwise CI covers it in Task 8.

- [ ] **Step 10: Full suite, lint, commit**

Run: `venv/Scripts/python -m pytest && venv/Scripts/python -m ruff check .`
Expected: all PASS / SKIPPED as above, lint clean.

```bash
git add .gitattributes deploy tests/test_deploy_files.py tests/test_deploy_script.py
git commit -m "feat: systemd units, install script and health-checked deploy script

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `requirements-dev.txt`, `pyproject.toml` (Task 1); `DATABASE_URL` handling in `tests/conftest.py` (Task 3, which fails rather than skips when `CI` is set); `deploy/deploy.sh` (Task 7, run through the deploy key's forced command).
- Produces: required secrets in the GitHub `production` environment: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`, and optionally `DEPLOY_PORT`. Task 9 documents them.

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: craig_test
          POSTGRES_PASSWORD: craig_test
          POSTGRES_DB: craig_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U craig_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      DATABASE_URL: postgresql://craig_test:craig_test@localhost:5432/craig_test
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v6
        with:
          python-version: '3.12'
          cache: pip
          cache-dependency-path: |
            requirements.txt
            requirements-dev.txt

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Lint
        run: ruff check .

      - name: Check shell scripts
        run: shellcheck deploy/*.sh

      - name: Test
        run: pytest

  deploy:
    needs: test
    if: github.event_name == 'push' && github.ref == 'refs/heads/Main'
    runs-on: ubuntu-latest
    environment: production
    concurrency:
      group: production
      cancel-in-progress: false
    steps:
      - name: Configure SSH
        env:
          DEPLOY_SSH_KEY: ${{ secrets.DEPLOY_SSH_KEY }}
          DEPLOY_KNOWN_HOSTS: ${{ secrets.DEPLOY_KNOWN_HOSTS }}
        run: |
          install -m 700 -d ~/.ssh
          printf '%s\n' "$DEPLOY_SSH_KEY" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > ~/.ssh/known_hosts

      # The deploy key is restricted on the server to run deploy/deploy.sh, so no remote command is passed
      - name: Deploy
        env:
          DEPLOY_HOST: ${{ secrets.DEPLOY_HOST }}
          DEPLOY_USER: ${{ secrets.DEPLOY_USER }}
          DEPLOY_PORT: ${{ secrets.DEPLOY_PORT }}
        run: |
          ssh -i ~/.ssh/deploy_key -p "${DEPLOY_PORT:-22}" \
            -o StrictHostKeyChecking=yes -o BatchMode=yes \
            "$DEPLOY_USER@$DEPLOY_HOST"
```

- [ ] **Step 2: Check the YAML parses**

Run: `venv/Scripts/python -c "import yaml" 2>/dev/null || venv/Scripts/python -m pip install --quiet pyyaml; venv/Scripts/python -c "import yaml; d = yaml.safe_load(open('.github/workflows/ci.yml')); print(sorted(d['jobs']))"`
Expected: prints `['deploy', 'test']`. (PyYAML is only a local check tool here. Do not add it to any requirements file.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run lint and tests on every push, deploy Main over SSH when green

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Documentation and retiring `run.sh`

**Files:**
- Create: `deploy/README.md`
- Modify: `README.md`, `example.env`
- Delete: `run.sh`

**Interfaces:**
- Consumes: everything from Tasks 1–8 (file names, env vars, secrets, commands). The docs must match them exactly.

- [ ] **Step 1: Write `deploy/README.md`**

````markdown
# Deploying CraigBot

Pushes to `Main` run the test suite on GitHub Actions. If it passes, the `deploy` job SSHes into the
server, and the deploy key's forced command runs `deploy/deploy.sh`. That script:

1. `git pull --ff-only` (fails if the server checkout has local changes or has diverged)
2. `venv/bin/pip install -r requirements.txt`
3. `sudo systemctl restart craigbot-celery craigbot`
4. Waits ~20s and checks that both services are active with a stable PID. If not, it prints their
   recent logs and fails the GitHub run.

The bot (`craigbot.service`) and Celery worker (`craigbot-celery.service`) run under systemd. They
restart automatically, including after `!restart`, start on boot, and log to the journal. The Celery
unit upgrades `yt-dlp` each time it starts, so YouTube changes don't break downloads.

## One-time server setup

Run these on the server as the user that owns the bot checkout (the one that currently runs `screen`).

1. **Get the deploy files:** `cd ~/CraigBot && git pull`
2. **Install the services:** `sudo deploy/install-services.sh`
   This writes the units to `/etc/systemd/system/` with your user and path filled in, adds a sudoers
   rule allowing only `systemctl restart craigbot-celery craigbot`, adds you to `systemd-journal`,
   and enables both units at boot.
3. **Stop the old setup:**
   ```bash
   screen -ls                      # find the session running run.sh
   screen -S <session> -X quit     # stops run.sh and the bot
   pkill -f 'celery worker' || true
   ```
4. **Start the services:**
   ```bash
   sudo systemctl start craigbot-celery craigbot
   systemctl status craigbot craigbot-celery
   journalctl -u craigbot -f       # Ctrl+C to stop following
   ```

## Deploy key (GitHub Actions → server)

1. On your own machine, create a key used only for deploys:
   ```bash
   ssh-keygen -t ed25519 -f craigbot_deploy -N "" -C github-actions-deploy
   ```
2. On the server, add the **public** key (`craigbot_deploy.pub`) to `~/.ssh/authorized_keys` on one
   line, restricted so it can only run the deploy script (use your real checkout path):
   ```text
   command="/home/<user>/CraigBot/deploy/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA... github-actions-deploy
   ```
3. Capture the server's host key so GitHub can verify it's talking to your server:
   ```bash
   ssh-keyscan -p 22 your.server.example
   ```
   Compare the fingerprint with `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the server.
4. Test it from your machine: `ssh -i craigbot_deploy <user>@your.server.example`. It should run a
   deploy and finish with `healthy` for both services.

## GitHub configuration

In the repo: **Settings → Environments → New environment → `production`**. Optionally limit it to
the `Main` branch. Add these environment secrets:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | Server hostname or IP |
| `DEPLOY_USER` | The bot's user on the server |
| `DEPLOY_PORT` | SSH port (optional, defaults to 22) |
| `DEPLOY_SSH_KEY` | Contents of the **private** key file `craigbot_deploy` |
| `DEPLOY_KNOWN_HOSTS` | Output of the `ssh-keyscan` command |

Or with the GitHub CLI: `gh secret set DEPLOY_SSH_KEY --env production < craigbot_deploy`, and so on.

Then re-run the latest failed `CI` workflow (**Actions → CI → Re-run jobs**) or push a commit.

## Day to day

- **Logs:** `journalctl -u craigbot -f`, `journalctl -u craigbot-celery -f`
- **Restart:** `sudo systemctl restart craigbot-celery craigbot` (or `!restart` in Discord)
- **Deploy by hand:** `~/CraigBot/deploy/deploy.sh`
- **Roll back:** `git revert <sha>` and push to `Main`. The revert deploys like any other commit.
- **Deploy failed with "Not possible to fast-forward":** the server checkout has local changes (often
  `cookies.txt`). Check them with `git status` on the server, then commit or discard them.
````

- [ ] **Step 2: Update `example.env`**

Replace the file contents with:
```text
BOT_TOKEN=<my_bot_token>
DB_USERNAME=<db_user>
DB_PASSWORD=<db_password>
DB_DATABASE_NAME=<db_name>

# Optional overrides (defaults shown)
# DB_HOST=localhost
# DB_PORT=5432
# DATABASE_URL=postgresql://user:password@host:5432/dbname   # replaces all DB_* settings
# REDIS_URL=redis://localhost:6379
```

- [ ] **Step 3: Update `README.md`**

Make these edits:

1. In **Prerequisites**, replace `- Python 3.8+` with `- Python 3.12`, and add `- PostgreSQL and Redis`.
2. Replace the **Installation** code block with:
   ```bash
   git clone https://github.com/hinkers/CraigBot.git
   cd CraigBot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp example.env prod.env   # or dev.env, used when craig_debug=true
   # Edit the env file with your configuration
   ```
3. Replace the **Configuration** section body with:
   ```markdown
   The bot reads `prod.env`, or `dev.env` when the `craig_debug=true` environment variable is set.
   See `example.env` for every setting:

   - `BOT_TOKEN`: Discord bot token
   - `DB_USERNAME`, `DB_PASSWORD`, `DB_DATABASE_NAME`: PostgreSQL credentials
   - `DB_HOST` / `DB_PORT`: optional, default `localhost` / `5432`
   - `DATABASE_URL`: optional full Postgres URL that replaces the `DB_*` settings
   - `REDIS_URL`: optional, default `redis://localhost:6379`
   ```
4. Replace the **Usage** section body with:
   ~~~markdown
   In production the bot and its Celery worker run as systemd services and deploy automatically
   when `Main` passes CI. See [deploy/README.md](deploy/README.md).

   To run locally, start the worker and the bot in two terminals:
   ```bash
   celery -A audio.tasks worker --concurrency=1
   python app.py
   ```
   ~~~
5. Add a new **Testing** section after Usage (and add `- [Testing](#testing)` to the table of contents after Usage):
   ~~~markdown
   ## Testing
   ```bash
   pip install -r requirements-dev.txt
   docker compose -f docker-compose.test.yml up -d --wait   # throwaway Postgres on port 5433
   pytest
   ruff check .
   ```
   Without the test database running, database tests are skipped and the rest still run. Tests
   refuse to touch any database whose name doesn't contain `test`. CI runs everything on every push
   and pull request.
   ~~~
6. In **Project structure**, remove the `run.sh` line and add these two lines in alphabetical order among the folders:
   ```text
   ├── deploy/                # systemd units and deploy script
   ├── tests/                 # pytest suite
   ```

- [ ] **Step 4: Delete `run.sh`**

Run: `git rm run.sh`

- [ ] **Step 5: Check docs against the code**

Run: `grep -rn "run.sh" --exclude-dir=venv --exclude-dir=.git --exclude-dir=docs . ; grep -n "DEPLOY_" .github/workflows/ci.yml deploy/README.md`
Expected: no `run.sh` matches outside `docs/` (apart from deploy/README.md's mention in "Stop the old setup"). Every `DEPLOY_*` secret used in `ci.yml` appears in the deploy README's table.

- [ ] **Step 6: Full suite, lint, commit**

Run: `venv/Scripts/python -m pytest && venv/Scripts/python -m ruff check .`

```bash
git add README.md example.env deploy/README.md
git commit -m "docs: document configuration, testing and deployment; remove run.sh

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Verify in CI and hand over

**Files:** none (verification and handover only)

- [ ] **Step 1: Ask the user before pushing**

Pushing the branch is outward-facing. Ask for explicit permission to run `git push -u origin feature/tests-and-deploy`. If they decline, stop here and report locally verified results.

- [ ] **Step 2: Push and watch CI**

Run: `git push -u origin feature/tests-and-deploy && gh run watch --exit-status`
Expected: the `test` job passes, including the 5 `test_deploy_script.py` tests and the shellcheck step. The `deploy` job is **skipped**, because this isn't `Main`. If shellcheck or Linux-only tests fail, fix them on the branch and push again.

- [ ] **Step 3: Final review and handover**

Use superpowers:finishing-a-development-branch. The handover message to the user must include:
- That merging to `Main` will run a deploy job that **fails until the server setup and secrets are done**. That failure is expected and harmless, and the running bot is unaffected.
- The ordered checklist from `deploy/README.md`: install the services, stop `screen`, set up the deploy key, add the GitHub secrets, re-run the job.
- The bugs fixed along the way (playlist share links, no-result search, empty tag list, "am i" crash), plus any `xfail` tests that were added.
- The follow-up still open: consider untracking `cookies.txt`.
