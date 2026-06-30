import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

print("DISCORD TOKEN FOUND:", bool(DISCORD_TOKEN))
print("DATABASE URL FOUND:", bool(DATABASE_URL))

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN")

if not DATABASE_URL:
    raise RuntimeError("Missing DATABASE_URL")