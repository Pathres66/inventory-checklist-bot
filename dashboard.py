import discord
from collections import defaultdict

import database
from models import STATUS_LABELS, STATUS_NAMES, STATUS_READY, STATUS_MISSING, STATUS_PROGRESS


class DashboardView(discord.ui.View):
    def __init__(self, bot, event_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.event_id = event_id

    @discord.ui.button(label="Pridať", emoji="➕", style=discord.ButtonStyle.success)
    async def add_single(self, interaction: discord.Interaction, button: discord.ui.Button):
        from checklist_views import AddItemView

        await interaction.response.send_message(
            "Vyber člena, ktorému chceš pridať jeden item:",
            view=AddItemView(self.bot, self.event_id, mode="single"),
            ephemeral=True,
            delete_after=60
        )

    @discord.ui.button(label="Bulk add", emoji="📥", style=discord.ButtonStyle.success)
    async def add_bulk(self, interaction: discord.Interaction, button: discord.ui.Button):
        from checklist_views import AddItemView

        await interaction.response.send_message(
            "Vyber člena, ktorému chceš pridať viac itemov naraz:",
            view=AddItemView(self.bot, self.event_id, mode="bulk"),
            ephemeral=True,
            delete_after=60
        )

    @discord.ui.button(label="Upraviť", emoji="⚙️", style=discord.ButtonStyle.primary)
    async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        from checklist_views import ChecklistMenuView

        await interaction.response.send_message(
            "⚙️ Úprava checklistu",
            view=ChecklistMenuView(self.bot, self.event_id),
            ephemeral=True,
            delete_after=60
        )

    @discord.ui.button(label="Moje itemy", emoji="👤", style=discord.ButtonStyle.secondary)
    async def my_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = await database.get_user_items(self.event_id, interaction.user.id)

        if not items:
            await interaction.response.send_message("Nemáš priradené žiadne itemy.", ephemeral=True, delete_after=5)
            return

        lines = [
            f"{STATUS_LABELS.get(item['status'], '❔')} `{item['id']}` — {item['item_name']}"
            for item in items
        ]

        embed = discord.Embed(
            title="📦 Tvoje itemy",
            description="\n".join(lines),
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30)

    @discord.ui.button(label="Refresh", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await refresh_dashboard(self.bot, self.event_id)
        await interaction.response.send_message("🔄 Dashboard obnovený.", ephemeral=True, delete_after=3)


def build_dashboard_embed(event, items):
    title = f"📦 {event['name']} — LOGISTIKA"

    if event["event_date"]:
        title += f"\n📅 {event['event_date']}"

    embed = discord.Embed(title=title, color=discord.Color.blue())

    if not items:
        embed.description = "Zatiaľ nie sú pridané žiadne itemy."
        embed.set_footer(text="Použi tlačidlá pod tabuľkou.")
        return embed

    grouped = defaultdict(list)

    for item in items:
        grouped[item["assigned_display_name"]].append(item)

    ready_count = sum(1 for item in items if item["status"] == STATUS_READY)
    missing_count = sum(1 for item in items if item["status"] == STATUS_MISSING)
    progress_count = sum(1 for item in items if item["status"] == STATUS_PROGRESS)

    for person, person_items in grouped.items():
        lines = []

        for item in person_items:
            icon = STATUS_LABELS.get(item["status"], "❔")
            lines.append(f"{icon} `{item['id']}` — {item['item_name']}")

        embed.add_field(name=f"👤 {person}", value="\n".join(lines), inline=False)

    embed.add_field(
        name="📊 Súhrn",
        value=(
            f"✅ {STATUS_NAMES[STATUS_READY]}: **{ready_count}**\n"
            f"❌ {STATUS_NAMES[STATUS_MISSING]}: **{missing_count}**\n"
            f"⏳ {STATUS_NAMES[STATUS_PROGRESS]}: **{progress_count}**"
        ),
        inline=False
    )

    embed.set_footer(text="Tabuľka sa aktualizuje automaticky. Ovládanie je cez tlačidlá nižšie.")
    return embed


async def refresh_dashboard(bot: discord.Client, event_id: int):
    pool = database.get_pool()

    async with pool.acquire() as conn:
        event = await conn.fetchrow("SELECT * FROM events WHERE id = $1", event_id)

    if not event or not event["channel_id"] or not event["dashboard_message_id"]:
        return

    channel = bot.get_channel(event["channel_id"])

    if channel is None:
        try:
            channel = await bot.fetch_channel(event["channel_id"])
        except discord.NotFound:
            return

    try:
        message = await channel.fetch_message(event["dashboard_message_id"])
    except discord.NotFound:
        await recreate_dashboard(bot, event)
        return

    items = await database.get_items(event_id)
    embed = build_dashboard_embed(event, items)

    await message.edit(embed=embed, view=DashboardView(bot, event_id))


async def recreate_dashboard(bot: discord.Client, event):
    channel = bot.get_channel(event["channel_id"])

    if channel is None:
        try:
            channel = await bot.fetch_channel(event["channel_id"])
        except discord.NotFound:
            return

    items = await database.get_items(event["id"])
    embed = build_dashboard_embed(event, items)

    message = await channel.send(embed=embed, view=DashboardView(bot, event["id"]))
    await database.set_dashboard_message(event["id"], channel.id, message.id)


async def create_or_update_dashboard(interaction: discord.Interaction, event):
    items = await database.get_items(event["id"])
    embed = build_dashboard_embed(event, items)
    view = DashboardView(interaction.client, event["id"])

    if event["channel_id"] and event["dashboard_message_id"]:
        channel = interaction.guild.get_channel(event["channel_id"])

        if channel:
            try:
                message = await channel.fetch_message(event["dashboard_message_id"])
                await message.edit(embed=embed, view=view)
                return message
            except discord.NotFound:
                pass

    message = await interaction.channel.send(embed=embed, view=view)
    await database.set_dashboard_message(event["id"], interaction.channel.id, message.id)

    return message