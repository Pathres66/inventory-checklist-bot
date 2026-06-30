import asyncpg
from config import DATABASE_URL

pool: asyncpg.Pool | None = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT,
                dashboard_message_id BIGINT,
                name TEXT NOT NULL,
                event_date TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS checklist_items (
                id SERIAL PRIMARY KEY,
                event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
                assigned_user_id BIGINT NOT NULL,
                assigned_display_name TEXT NOT NULL,
                item_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'missing',
                note TEXT,
                created_by BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    return pool


async def get_active_event(guild_id: int):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM events
            WHERE guild_id = $1 AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, guild_id)


async def get_event_by_dashboard_message(message_id: int):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM events
            WHERE dashboard_message_id = $1 AND is_active = TRUE
            LIMIT 1
        """, message_id)


async def create_event(guild_id: int, name: str, event_date: str | None):
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE events
            SET is_active = FALSE
            WHERE guild_id = $1 AND is_active = TRUE
        """, guild_id)

        return await conn.fetchrow("""
            INSERT INTO events (guild_id, name, event_date, is_active)
            VALUES ($1, $2, $3, TRUE)
            RETURNING *
        """, guild_id, name, event_date)


async def close_active_event(guild_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE events
            SET is_active = FALSE
            WHERE guild_id = $1 AND is_active = TRUE
        """, guild_id)


async def set_dashboard_message(event_id: int, channel_id: int, message_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE events
            SET channel_id = $1, dashboard_message_id = $2
            WHERE id = $3
        """, channel_id, message_id, event_id)


async def add_item(event_id: int, assigned_user_id: int, assigned_display_name: str, item_name: str, created_by: int):
    async with get_pool().acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO checklist_items (
                event_id, assigned_user_id, assigned_display_name,
                item_name, status, created_by
            )
            VALUES ($1, $2, $3, $4, 'missing', $5)
            RETURNING *
        """, event_id, assigned_user_id, assigned_display_name, item_name, created_by)


async def bulk_add_items(event_id: int, assigned_user_id: int, assigned_display_name: str, item_names: list[str], created_by: int):
    async with get_pool().acquire() as conn:
        for item_name in item_names:
            await conn.execute("""
                INSERT INTO checklist_items (
                    event_id, assigned_user_id, assigned_display_name,
                    item_name, status, created_by
                )
                VALUES ($1, $2, $3, $4, 'missing', $5)
            """, event_id, assigned_user_id, assigned_display_name, item_name, created_by)


async def get_items(event_id: int):
    async with get_pool().acquire() as conn:
        return await conn.fetch("""
            SELECT *
            FROM checklist_items
            WHERE event_id = $1
            ORDER BY assigned_display_name ASC, item_name ASC
        """, event_id)


async def get_user_items(event_id: int, user_id: int):
    async with get_pool().acquire() as conn:
        return await conn.fetch("""
            SELECT *
            FROM checklist_items
            WHERE event_id = $1 AND assigned_user_id = $2
            ORDER BY item_name ASC
        """, event_id, user_id)


async def update_item_status(item_id: int, status: str):
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE checklist_items
            SET status = $1, updated_at = NOW()
            WHERE id = $2
        """, status, item_id)


async def rename_item(item_id: int, new_name: str):
    async with get_pool().acquire() as conn:
        await conn.execute("""
            UPDATE checklist_items
            SET item_name = $1, updated_at = NOW()
            WHERE id = $2
        """, new_name, item_id)


async def delete_item(item_id: int):
    async with get_pool().acquire() as conn:
        await conn.execute("""
            DELETE FROM checklist_items
            WHERE id = $1
        """, item_id)