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
