import asyncio
import discord
from discord.ext import commands

from config import DISCORD_TOKEN
from database import init_db, get_event_by_dashboard_message, get_active_event
from dashboard import recreate_dashboard, bump_dashboard_to_bottom


DASHBOARD_BUMP_DELAY = 20


class LarpChecklistBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.messages = True
        intents.message_content = True

        super().__init__(command_prefix="!", intents=intents)

        self.dashboard_bump_tasks: dict[int, asyncio.Task] = {}
        self.intentional_dashboard_deletes: set[int] = set()

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

        if message.id in self.intentional_dashboard_deletes:
            self.intentional_dashboard_deletes.discard(message.id)
            return

        event = await get_event_by_dashboard_message(message.id)

        if not event:
            return

        await recreate_dashboard(self, event)

    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return

        if message.author.bot:
            return

        event = await get_active_event(message.guild.id)

        if not event:
            return

        if not event["channel_id"] or message.channel.id != event["channel_id"]:
            return

        event_id = event["id"]

        old_task = self.dashboard_bump_tasks.get(event_id)

        if old_task and not old_task.done():
            old_task.cancel()

        self.dashboard_bump_tasks[event_id] = asyncio.create_task(
            self.delayed_dashboard_bump(event_id)
        )

    async def delayed_dashboard_bump(self, event_id: int):
        try:
            await asyncio.sleep(DASHBOARD_BUMP_DELAY)
            await bump_dashboard_to_bottom(self, event_id)
        except asyncio.CancelledError:
            pass


bot = LarpChecklistBot()
bot.run(DISCORD_TOKEN)