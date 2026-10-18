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
