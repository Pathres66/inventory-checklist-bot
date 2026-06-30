import discord
from discord.ext import commands

from config import DISCORD_TOKEN
from database import init_db, get_event_by_dashboard_message
from dashboard import recreate_dashboard


class LarpChecklistBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True

        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await init_db()
        await self.load_extension("commands")
        await self.tree.sync()
        print("Slash commands synced.")

    async def on_ready(self):
        print(f"Bot je online ako {self.user}")

    async def on_message_delete(self, message: discord.Message):
        if message.guild is None:
            return

        event = await get_event_by_dashboard_message(message.id)

        if not event:
            return

        await recreate_dashboard(self, event)


bot = LarpChecklistBot()
bot.run(DISCORD_TOKEN)