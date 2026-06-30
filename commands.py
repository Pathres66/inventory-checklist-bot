import discord
from discord import app_commands
from discord.ext import commands

import database
from dashboard import create_or_update_dashboard, refresh_dashboard
from models import STATUS_MISSING, STATUS_PROGRESS


class ChecklistCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="event_create", description="Vytvorí novú LARP akciu a checklist dashboard.")
    @app_commands.describe(nazov="Názov akcie", datum="Dátum akcie, napr. 12.7.2026")
    async def event_create(self, interaction: discord.Interaction, nazov: str, datum: str | None = None):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ Tento príkaz môže použiť iba admin alebo človek s Manage Server právom.",
                ephemeral=True,
                delete_after=5
            )
            return

        await interaction.response.defer(ephemeral=True)

        event = await database.create_event(interaction.guild.id, nazov, datum)
        await create_or_update_dashboard(interaction, event)

        await interaction.followup.send(
            f"✅ Akcia **{nazov}** bola vytvorená.",
            ephemeral=True
        )

    @app_commands.command(name="event_close", description="Ukončí aktuálnu aktívnu akciu.")
    async def event_close(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ Tento príkaz môže použiť iba admin alebo človek s Manage Server právom.",
                ephemeral=True,
                delete_after=5
            )
            return

        event = await database.get_active_event(interaction.guild.id)

        if not event:
            await interaction.response.send_message("❌ Nie je aktívna žiadna akcia.", ephemeral=True, delete_after=5)
            return

        await database.close_active_event(interaction.guild.id)

        await interaction.response.send_message(
            f"✅ Akcia **{event['name']}** bola ukončená.",
            ephemeral=True,
            delete_after=5
        )

    @app_commands.command(name="dashboard_refresh", description="Ručne obnoví checklist dashboard.")
    async def dashboard_refresh(self, interaction: discord.Interaction):
        event = await database.get_active_event(interaction.guild.id)

        if not event:
            await interaction.response.send_message("❌ Nie je aktívna žiadna akcia.", ephemeral=True, delete_after=5)
            return

        await refresh_dashboard(self.bot, event["id"])

        await interaction.response.send_message("🔄 Dashboard bol obnovený.", ephemeral=True, delete_after=5)

    @app_commands.command(name="finalcheck", description="Vypíše finálny checklist s vecami, ktoré ešte nie sú pripravené.")
    async def finalcheck(self, interaction: discord.Interaction):
        event = await database.get_active_event(interaction.guild.id)

        if not event:
            await interaction.response.send_message("❌ Nie je aktívna žiadna akcia.", ephemeral=True, delete_after=5)
            return

        items = await database.get_items(event["id"])

        problem_items = [
            item for item in items
            if item["status"] in [STATUS_MISSING, STATUS_PROGRESS]
        ]

        if not problem_items:
            await interaction.response.send_message(f"✅ **{event['name']}** — všetko je pripravené.")
            return

        grouped = {}

        for item in problem_items:
            grouped.setdefault(item["assigned_display_name"], []).append(item)

        lines = []

        for person, person_items in grouped.items():
            lines.append(f"**👤 {person}**")

            for item in person_items:
                icon = "❌" if item["status"] == STATUS_MISSING else "⏳"
                lines.append(f"{icon} {item['item_name']}")

            lines.append("")

        embed = discord.Embed(
            title=f"⚠️ FINAL CHECKLIST — {event['name']}",
            description="\n".join(lines),
            color=discord.Color.orange()
        )

        embed.set_footer(text="Zobrazuje iba veci, ktoré nie sú označené ako pripravené.")

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ChecklistCommands(bot))