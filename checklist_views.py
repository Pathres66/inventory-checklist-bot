import discord

import database
from dashboard import refresh_dashboard
from models import STATUS_READY, STATUS_MISSING, STATUS_PROGRESS, STATUS_LABELS, STATUS_NAMES


class AddItemModal(discord.ui.Modal, title="Pridať item"):
    item_name = discord.ui.TextInput(
        label="Názov itemu",
        placeholder="Napr. Batérie do rádia",
        max_length=100
    )

    def __init__(self, bot, event_id: int, assigned_user: discord.Member):
        super().__init__()
        self.bot = bot
        self.event_id = event_id
        self.assigned_user = assigned_user

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        await database.add_item(
            self.event_id,
            self.assigned_user.id,
            self.assigned_user.display_name,
            str(self.item_name),
            interaction.user.id
        )

        await refresh_dashboard(self.bot, self.event_id)

        await interaction.followup.send(
            "✅ Pridané.",
            ephemeral=True
        )


class BulkAddModal(discord.ui.Modal, title="Bulk pridať itemy"):
    items = discord.ui.TextInput(
        label="Itemy",
        placeholder="Každý item daj na nový riadok",
        style=discord.TextStyle.paragraph,
        max_length=1500
    )

    def __init__(self, bot, event_id: int, assigned_user: discord.Member):
        super().__init__()
        self.bot = bot
        self.event_id = event_id
        self.assigned_user = assigned_user

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        item_names = [
            line.strip()
            for line in str(self.items).splitlines()
            if line.strip()
        ]

        if not item_names:
            await interaction.followup.send(
                "❌ Nezadal si žiadne itemy.",
                ephemeral=True
            )
            return

        await database.bulk_add_items(
            self.event_id,
            self.assigned_user.id,
            self.assigned_user.display_name,
            item_names,
            interaction.user.id
        )

        await refresh_dashboard(self.bot, self.event_id)

        await interaction.followup.send(
            f"✅ Pridané itemy: **{len(item_names)}**",
            ephemeral=True
        )


class RenameItemModal(discord.ui.Modal, title="Premenovať item"):
    new_name = discord.ui.TextInput(
        label="Nový názov itemu",
        max_length=100
    )

    def __init__(self, bot, event_id: int, item_id: int):
        super().__init__()
        self.bot = bot
        self.event_id = event_id
        self.item_id = item_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        await database.rename_item(self.item_id, str(self.new_name))
        await refresh_dashboard(self.bot, self.event_id)

        await interaction.followup.send(
            "✏️ Item bol premenovaný.",
            ephemeral=True
        )


class UserSelectForAdd(discord.ui.UserSelect):
    def __init__(self, bot, event_id: int, mode: str):
        super().__init__(
            placeholder="Vyber člena tímu",
            min_values=1,
            max_values=1
        )
        self.bot = bot
        self.event_id = event_id
        self.mode = mode

    async def callback(self, interaction: discord.Interaction):
        selected_user = self.values[0]

        if not isinstance(selected_user, discord.Member):
            await interaction.response.send_message(
                "❌ Vybraný používateľ nie je člen servera.",
                ephemeral=True,
                delete_after=3
            )
            return

        if self.mode == "single":
            await interaction.response.send_modal(
                AddItemModal(self.bot, self.event_id, selected_user)
            )
        else:
            await interaction.response.send_modal(
                BulkAddModal(self.bot, self.event_id, selected_user)
            )


class AddItemView(discord.ui.View):
    def __init__(self, bot, event_id: int, mode: str):
        super().__init__(timeout=120)
        self.add_item(UserSelectForAdd(bot, event_id, mode))


class ItemSelect(discord.ui.Select):
    def __init__(self, bot, event_id: int, items, mode: str):
        self.bot = bot
        self.event_id = event_id
        self.mode = mode

        options = []

        for item in items[:25]:
            icon = STATUS_LABELS.get(item["status"], "❔")

            options.append(
                discord.SelectOption(
                    label=f"{item['assigned_display_name']} — {item['item_name']}"[:100],
                    description=STATUS_NAMES.get(item["status"], item["status"])[:100],
                    value=str(item["id"]),
                    emoji=icon
                )
            )

        super().__init__(
            placeholder="Vyber item",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        item_id = int(self.values[0])

        if self.mode == "status":
            await interaction.response.edit_message(
                content="Vyber nový stav:",
                view=StatusChangeView(self.bot, self.event_id, item_id)
            )

        elif self.mode == "delete":
            await database.delete_item(item_id)
            await refresh_dashboard(self.bot, self.event_id)

            await interaction.response.edit_message(
                content="🗑️ Item bol vymazaný.",
                view=None
            )
            await interaction.delete_original_response()

        elif self.mode == "rename":
            await interaction.response.send_modal(
                RenameItemModal(self.bot, self.event_id, item_id)
            )


class ItemSelectView(discord.ui.View):
    def __init__(self, bot, event_id: int, items, mode: str):
        super().__init__(timeout=120)
        self.add_item(ItemSelect(bot, event_id, items, mode))


class StatusButton(discord.ui.Button):
    def __init__(self, bot, event_id: int, item_id: int, status: str):
        super().__init__(
            label=STATUS_NAMES[status],
            emoji=STATUS_LABELS[status],
            style=discord.ButtonStyle.secondary
        )
        self.bot = bot
        self.event_id = event_id
        self.item_id = item_id
        self.status = status

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        await database.update_item_status(self.item_id, self.status)
        await refresh_dashboard(self.bot, self.event_id)

        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass

        await interaction.followup.send(
            "✅ Stav zmenený.",
            ephemeral=True
        )


class StatusChangeView(discord.ui.View):
    def __init__(self, bot, event_id: int, item_id: int):
        super().__init__(timeout=120)

        self.add_item(StatusButton(bot, event_id, item_id, STATUS_READY))
        self.add_item(StatusButton(bot, event_id, item_id, STATUS_PROGRESS))
        self.add_item(StatusButton(bot, event_id, item_id, STATUS_MISSING))


class ChecklistMenuView(discord.ui.View):
    def __init__(self, bot, event_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.event_id = event_id

    @discord.ui.button(label="Zmeniť stav", emoji="✅", style=discord.ButtonStyle.primary)
    async def change_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = await database.get_items(self.event_id)

        if not items:
            await interaction.response.edit_message(
                content="Zatiaľ nie sú žiadne itemy.",
                view=None
            )
            return

        await interaction.response.edit_message(
            content="Vyber item, ktorému chceš zmeniť stav:",
            view=ItemSelectView(self.bot, self.event_id, items, mode="status")
        )

    @discord.ui.button(label="Premenovať", emoji="✏️", style=discord.ButtonStyle.secondary)
    async def rename_item_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = await database.get_items(self.event_id)

        if not items:
            await interaction.response.edit_message(
                content="Zatiaľ nie sú žiadne itemy.",
                view=None
            )
            return

        await interaction.response.edit_message(
            content="Vyber item, ktorý chceš premenovať:",
            view=ItemSelectView(self.bot, self.event_id, items, mode="rename")
        )

    @discord.ui.button(label="Vymazať", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete_item_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = await database.get_items(self.event_id)

        if not items:
            await interaction.response.edit_message(
                content="Zatiaľ nie sú žiadne itemy.",
                view=None
            )
            return

        await interaction.response.edit_message(
            content="Vyber item, ktorý chceš vymazať:",
            view=ItemSelectView(self.bot, self.event_id, items, mode="delete")
        )