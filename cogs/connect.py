import asyncio
import json
import os
import urllib
from discord import DMChannel
from sqlalchemy import select

import websockets
from discord.ext import commands

from database.database import Base
from sqlalchemy.inspection import inspect


class ConnectCog(commands.Cog, name='Connect'):
    def __init__(self, bot):
        self.bot = bot
        self.connected_clients = set()
        self.message_handlers = {
            'send_message': self.send_message_to_id,
            'models.retrieve': self.models_retrieve,
            'models.all': self.models_all,
            'chat.types': self.chat_types
        }
        asyncio.create_task(self.start_websocket_server())

    @commands.Cog.listener()
    async def on_message(self, message):
        if isinstance(message.channel, DMChannel) and message.author != self.bot.user:
            await self.send_message(
                'chat.dm',
                dict(
                    author=dict(id=message.author.id, name=message.author.name),
                    message=str(message.content)
                )
            )

    async def websocket_server(self, websocket, path):
        query_params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(path).query))
        if query_params.get("token") != os.getenv('WEBSOCKET_TOKEN'):
            await websocket.close(code=4000, reason="Invalid token")
            return

        self.connected_clients.add(websocket)
        try:
            async for message in websocket:
                asyncio.run_coroutine_threadsafe(self.receive_message(message), self.bot.loop)
        except websockets.ConnectionClosedError:
            pass  # Handle disconnection
        finally:
            self.connected_clients.remove(websocket)

    async def send_message(self, event, data):
        for websocket in self.connected_clients:
            message = dict(event=event)
            if data is not None:
                message['data'] = data
            await websocket.send(json.dumps(message))

    async def receive_message(self, raw):
        message = json.loads(raw)
        event = message.get('event', None)
        data = message.get('data', None)
        print(raw)

        for name, message_handler in self.message_handlers.items():
            if event == name:                
                await message_handler(data)
            elif event.startswith(name):
                await message_handler(event[len(name):].lstrip('.'), data)

    async def send_message_to_id(self, data):
        if data['type_'] == 'Channel':
            channel = self.bot.get_channel(int(data['id']))
            if channel:
                await channel.send(data['message'])
        elif data['type_'] == 'Direct':
            member = await self.bot.fetch_user(int(data['id']))
            if member:
                await member.send(data['message'])

    async def models_retrieve(self, message):
        if message is not None:
            return

        models_info = {}
        for cls in Base._sa_registry._class_registry.values():
            if hasattr(cls, '__tablename__'):
                model_info = {}
                for attr in inspect(cls).mapper.column_attrs:
                    column = attr.expression
                    model_info[attr.key] = {
                        "type": str(column.type),
                        "nullable": column.nullable,
                        "default": str(column.default.arg) if column.default else None,
                        "max_length": column.type.length if hasattr(column.type, 'length') else None,
                        "primary_key": column.primary_key
                    }
                models_info[cls.__name__] = model_info

        await self.send_message('models.retrieve', json.dumps(models_info))

    async def models_all(self, model_name, data):
        if data is not None:
            return

        async with self.bot.session as session:
            model_class = Base._sa_registry._class_registry.get(model_name)
            if model_class is None:
                return None

            # Find the primary key column name
            primary_key_column = 'id'
            for attr in inspect(model_class).mapper.column_attrs:
                if attr.expression.primary_key:
                    primary_key_column = attr.key
                    break

            # Query all instances of the model
            statement = select(model_class)
            result = await session.execute(statement)
            instances = result.scalars()
            await self.send_message(
                f'models.all.{model_name}',
                {getattr(instance, primary_key_column): str(instance) for instance in instances}
            )

    async def chat_types(self, message):
        if message is not None:
            return
        
        data = {'Direct': {}, 'Guilds': []}

        # Getting member information from direct messages
        for user in self.bot.users:
            if not user.bot:
                data['Direct'][user.id] = user.name

        # Getting guild and channel information
        for guild in self.bot.guilds:
            guild_info = {
                'Name': guild.name,
                'Id': guild.id,
                'Channels': {}
            }
            for channel in guild.text_channels:
                guild_info['Channels'][channel.id] = channel.name
            for member in guild.members:
                data['Direct'][member.id] = member.name
            data['Guilds'].append(guild_info)

        await self.send_message('chat.types',  data)

    async def start_websocket_server(self):
        port = 8866
        if self.bot.debug:
            port = 6688
        await websockets.serve(self.websocket_server, "0.0.0.0", port)


async def setup(bot):
    await bot.add_cog(ConnectCog(bot))
