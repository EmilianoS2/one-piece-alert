import asyncio
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import tasks
from dotenv import load_dotenv

import scraper

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# Host containers run on UTC, which would shift the release-day window and the
# polling schedule. Resolve the zone explicitly so it's wrong loudly, not silently.
LOCAL_TZ = ZoneInfo(os.getenv("TZ", "America/Los_Angeles"))

# Overridable so a mounted volume can hold this across restarts — on an ephemeral
# filesystem a lost file makes the bot re-baseline and skip one chapter's alert.
LAST_CHAPTER_FILE = os.getenv("LAST_CHAPTER_FILE", "last_chapter.json")

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

# One Piece chapters only release Wed–Sat, so don't scrape on other days.
# (Python weekday(): Mon=0 … Sun=6)
RELEASE_DAYS = (2, 3, 4, 5)


@tasks.loop(minutes=30)
async def check_for_new_chapter():
    if datetime.now(LOCAL_TZ).weekday() not in RELEASE_DAYS:
        print("[Bot] No chapters release today — skipping check.")
        return

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

        message = f"<@&1477178126156169377> NEW CHAPTER ALERT! - {latest['url']}"

        await channel.send(message)
        save_last_chapter(latest)
        print(f"[Bot] Alert sent for: {latest['title']}")

    else:
        print(f"[Bot] No new chapter. Latest is still: {latest['title']}")


@check_for_new_chapter.before_loop
async def before_check():
    # Wait until the bot is fully connected before starting the loop
    await client.wait_until_ready()

    # Align the loop to the next :00:45 or :30:45 wall-clock mark so polling lines
    # up with TCB's release times, regardless of when the bot was started. The 45s
    # offset gives the site a moment to actually publish before we scrape.
    now = datetime.now(LOCAL_TZ)
    next_mark = now.replace(second=45, microsecond=0) + timedelta(minutes=(-now.minute) % 30)
    if next_mark <= now:
        next_mark += timedelta(minutes=30)

    wait_seconds = (next_mark - now).total_seconds()
    print(f"[Bot] Syncing to the clock — waiting {wait_seconds:.0f}s until {next_mark:%H:%M:%S}.")
    await asyncio.sleep(wait_seconds)


# ── Entry point ────────────────────────────────────────────────────────────────

client.run(DISCORD_TOKEN)
