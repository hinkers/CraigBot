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
