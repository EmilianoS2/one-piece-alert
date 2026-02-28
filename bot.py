import json
import os

import discord
from discord.ext import tasks
from dotenv import load_dotenv

import scraper

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
LAST_CHAPTER_FILE = "last_chapter.json"

intents = discord.Intents.default()
client = discord.Client(intents=intents)


# ── Persistence helpers ────────────────────────────────────────────────────────

def load_last_chapter():
    """Load the last known chapter from disk. Returns None if file doesn't exist."""
    if os.path.exists(LAST_CHAPTER_FILE):
        with open(LAST_CHAPTER_FILE, "r") as f:
            return json.load(f)
    return None


def save_last_chapter(chapter: dict):
    """Persist the latest chapter info to disk."""
    with open(LAST_CHAPTER_FILE, "w") as f:
        json.dump(chapter, f, indent=2)


# ── Discord events ─────────────────────────────────────────────────────────────

@client.event
async def on_ready():
    print(f"[Bot] Logged in as {client.user}")

    # On first run, save the current chapter without alerting.
    # This prevents a false alert the very first time the bot starts.
    if not os.path.exists(LAST_CHAPTER_FILE):
        print("[Bot] First run — saving current chapter to avoid a false alert.")
        latest = scraper.get_latest_chapter()
        if latest:
            save_last_chapter(latest)
            print(f"[Bot] Saved baseline chapter: {latest['title']}")
        else:
            print("[Bot] Warning: could not fetch current chapter on startup. "
                  "Will retry on next polling cycle.")

    if not check_for_new_chapter.is_running():
        check_for_new_chapter.start()


# ── Polling task ───────────────────────────────────────────────────────────────

@tasks.loop(minutes=15)
async def check_for_new_chapter():
    print("[Bot] Checking for new chapter...")

    latest = scraper.get_latest_chapter()
    if latest is None:
        print("[Bot] Scraper returned no data — skipping this cycle.")
        return

    last = load_last_chapter()

    if last is None or latest["id"] != last["id"]:
        print(f"[Bot] New chapter detected: {latest['title']}")

        channel = client.get_channel(CHANNEL_ID)
        if channel is None:
            print(f"[Bot] Could not find channel ID {CHANNEL_ID}. "
                  "Check that the bot has access to the channel.")
            return

        # Change "@everyone" to "@here" or remove it if you don't want a ping
        message = (
            f"@everyone\n"
            f"**A new One Piece chapter is out!**\n"
            f"**{latest['title']}**\n"
            f"{latest['url']}"
        )

        await channel.send(message)
        save_last_chapter(latest)
        print(f"[Bot] Alert sent for: {latest['title']}")

    else:
        print(f"[Bot] No new chapter. Latest is still: {latest['title']}")


@check_for_new_chapter.before_loop
async def before_check():
    # Wait until the bot is fully connected before starting the loop
    await client.wait_until_ready()


# ── Entry point ────────────────────────────────────────────────────────────────

client.run(DISCORD_TOKEN)
