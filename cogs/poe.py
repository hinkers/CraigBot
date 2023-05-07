import base64
import csv
import re

import aiohttp
from discord.ext import commands
from prettytable import PrettyTable
from datetime import datetime


class PoeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_sync = datetime.min
        self.headers = None
        self.csv_data = None

    async def poe_get_csv_data(self):
        if self.last_sync.date() == datetime.now().date():
            return
        csv_data = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://divcards.io/mapdata.js') as response:
                    if response.status == 200:
                        csv_data = await response.text()
                        if csv_data:
                            pattern = r"var mapData = '(.+?)';"
                            match = re.search(pattern, csv_data, re.DOTALL)
                            if match:
                                csv_data = base64.b64decode(match.group(1) + '==')
                                rows = csv_data.strip().split(b'\n')
                                rows = list(map(lambda r: r.strip().decode(), rows))
                                self.headers = rows[0].split(',')
                                csv_data = [dict(row) for row in csv.DictReader(rows)]
        except Exception:
            pass
        self.csv_data = csv_data

    def poe_by_map(self, map_name):
        matching_rows = [row for row in self.csv_data if map_name.lower() in row[self.headers[0]].lower()]
        if matching_rows:
            table = PrettyTable(self.headers[1:5])
            table.align = "l"
            for row in matching_rows:
                table.add_row([row[self.headers[1]], row[self.headers[2]], row[self.headers[3]], row[self.headers[4]]])
            return str(table)
        else:
            return ''

    def poe_by_card(self, card_name):
        matching_rows = [row for row in self.csv_data if card_name.lower() in row[self.headers[1]].lower()]
        if matching_rows:
            table = PrettyTable(self.headers[0:1] + self.headers[2:5])
            table.align = "l"
            for row in matching_rows:
                table.add_row([row[self.headers[0]], row[self.headers[2]], row[self.headers[3]], row[self.headers[4]]])
            return str(table)
        else:
            return ''

    @commands.hybrid_command()
    async def poe(self, ctx: commands.context, query: str):
        """ Search for what diviation cards will drop on a map or what maps a divication card will drop on. """
        await ctx.typing(ephemeral=True)
        await self.poe_get_csv_data()
        if self.csv_data is None:
            await ctx.send('Unable to scam https://divcards.io/')
            return
        maps = self.poe_by_map(query)
        if maps != '':
            await ctx.send(f'```{maps}```', ephemeral=True)
            return
        cards = self.poe_by_card(query)
        if cards != '':
            await ctx.send(f'```{cards}```', ephemeral=True)
            return
        await ctx.send('No results found.', ephemeral=True)


async def setup(bot):
    await bot.add_cog(PoeCog(bot))
