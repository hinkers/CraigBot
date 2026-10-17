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
