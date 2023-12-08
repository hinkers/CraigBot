import aiohttp
from discord.ext import commands


class ChatbotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ollama_url = "http://localhost:11434/api/generate"  # Replace with the actual Ollama API URL if different

    async def get_ollama_response(self, prompt):
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "llama2",  # Replace with your desired model
                "prompt": prompt,
                "format": "json"  # Assuming you want a JSON response
            }
            async with session.post(self.ollama_url, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"response": "Sorry, I couldn't understand the dumb shit you said."}

    @commands.Cog.listener()
    async def on_message(self, message):
        # Don't respond to messages sent by the bot itself
        if message.author == self.bot.user:
            return

        # Check if the bot is mentioned
        if self.bot.user in message.mentions:
            response_data = await self.get_ollama_response(message.content)
            response = response_data.get("response", "Sorry, are you some kind of idiot?")
            await message.channel.send(response)


async def setup(bot):
    return
    await bot.add_cog(ChatbotCog(bot))