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
