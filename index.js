# ========================================================
# Trademark IBRAA – All rights reserved.
# This bot is protected under IBRAA intellectual property.
# ========================================================

import discord
from discord.ext import commands
import json
import os
import asyncio
from typing import Optional, List

# ---------- CONFIG ----------
CONFIG_FILE = "config.json"
DATA_FILE = "data.json"

if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(
        f"Missing {CONFIG_FILE}. Copy config.json.example to config.json and add your token."
    )

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)
TOKEN = config.get("token")
if not TOKEN:
    raise ValueError("Bot token not found in config.json")

# ---------- DATA MANAGER ----------
class DataManager:
    """Thread‑safe JSON storage for guild settings."""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._lock = asyncio.Lock()
        self._data = {}
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}
        else:
            self._data = {}
        if "guilds" not in self._data:
            self._data["guilds"] = {}

    async def save(self):
        async with self._lock:
            try:
                with open(self.filepath, "w") as f:
                    json.dump(self._data, f, indent=4)
            except IOError as e:
                print(f"❌ Failed to save data: {e}")

    def get_guild_data(self, guild_id: int) -> dict:
        gid = str(guild_id)
        if gid not in self._data["guilds"]:
            self._data["guilds"][gid] = {
                "keywords": [],
                "log_channel": None
            }
        return self._data["guilds"][gid]

    async def add_keyword(self, guild_id: int, keyword: str) -> bool:
        data = self.get_guild_data(guild_id)
        kw = keyword.lower()
        if kw in data["keywords"]:
            return False
        data["keywords"].append(kw)
        await self.save()
        return True

    async def remove_keyword(self, guild_id: int, keyword: str) -> bool:
        data = self.get_guild_data(guild_id)
        kw = keyword.lower()
        if kw not in data["keywords"]:
            return False
        data["keywords"].remove(kw)
        await self.save()
        return True

    def list_keywords(self, guild_id: int) -> List[str]:
        return self.get_guild_data(guild_id)["keywords"].copy()

    async def set_log_channel(self, guild_id: int, channel_id: Optional[int]):
        data = self.get_guild_data(guild_id)
        data["log_channel"] = channel_id
        await self.save()

    def get_log_channel(self, guild_id: int) -> Optional[int]:
        return self.get_guild_data(guild_id).get("log_channel")

# ---------- BOT SETUP ----------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
data_manager = DataManager(DATA_FILE)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"📁 Data file: {DATA_FILE}")
    print(f"🔷 Trademark IBRAA – All rights reserved.")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    keywords = data_manager.list_keywords(message.guild.id)
    if not keywords:
        return

    content_lower = message.content.lower()
    matched = [kw for kw in keywords if kw in content_lower]
    if not matched:
        return

    log_channel_id = data_manager.get_log_channel(message.guild.id)
    if log_channel_id:
        channel = message.guild.get_channel(log_channel_id)
        if channel:
            embed = discord.Embed(
                title="🔍 Keyword Detected",
                description=f"**{message.author.mention}** said:",
                color=discord.Color.orange()
            )
            embed.add_field(name="Message", value=message.content[:1024], inline=False)
            embed.add_field(name="Matched Keywords", value=", ".join(f"`{kw}`" for kw in matched), inline=False)
            embed.add_field(name="Jump", value=f"[Click here]({message.jump_url})", inline=False)
            embed.set_footer(text=f"Channel: #{message.channel.name} • Trademark IBRAA")
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                print(f"⚠️ Missing permissions to send to log channel in {message.guild.name}")
        else:
            print(f"⚠️ Log channel {log_channel_id} not found in {message.guild.name}")

# ---------- COMMANDS ----------
@bot.command(name="addkeyword", aliases=["addkw"])
@commands.has_permissions(administrator=True)
async def add_keyword(ctx, *, keyword: str):
    if len(keyword) < 2:
        await ctx.send("❌ Keyword must be at least 2 characters.")
        return
    success = await data_manager.add_keyword(ctx.guild.id, keyword)
    if success:
        await ctx.send(f"✅ Keyword `{keyword}` added.")
    else:
        await ctx.send(f"❌ Keyword `{keyword}` already exists.")

@bot.command(name="removekeyword", aliases=["rmkw"])
@commands.has_permissions(administrator=True)
async def remove_keyword(ctx, *, keyword: str):
    success = await data_manager.remove_keyword(ctx.guild.id, keyword)
    if success:
        await ctx.send(f"✅ Keyword `{keyword}` removed.")
    else:
        await ctx.send(f"❌ Keyword `{keyword}` not found.")

@bot.command(name="listkeywords", aliases=["listkw", "keywords"])
async def list_keywords(ctx):
    keywords = data_manager.list_keywords(ctx.guild.id)
    if not keywords:
        await ctx.send("📭 No keywords are currently being tracked.")
        return
    kw_list = "\n".join(f"• `{kw}`" for kw in keywords)
    await ctx.send(f"📋 Tracked keywords ({len(keywords)}):\n{kw_list}")

@bot.command(name="setlogchannel", aliases=["setlog"])
@commands.has_permissions(administrator=True)
async def set_log_channel(ctx, channel: discord.TextChannel = None):
    if channel is None:
        await data_manager.set_log_channel(ctx.guild.id, None)
        await ctx.send("🔕 Keyword alerts disabled.")
    else:
        await data_manager.set_log_channel(ctx.guild.id, channel.id)
        await ctx.send(f"📢 Keyword alerts will be sent to {channel.mention}")

# Error handling
@add_keyword.error
@remove_keyword.error
@set_log_channel.error
async def command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need administrator permissions to use this command.")
    else:
        await ctx.send(f"⚠️ An error occurred: {error}")

# ---------- START BOT ----------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid bot token. Please check config.json.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
