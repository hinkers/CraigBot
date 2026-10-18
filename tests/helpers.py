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
