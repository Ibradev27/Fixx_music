# ══════════════════════════════════════════════════════════════════════════════
#  ██╗██████╗ ██████╗  █████╗  █████╗ 
#  ██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗
#  ██║██████╔╝██████╔╝███████║███████║
#  ██║██╔══██╗██╔══██╗██╔══██║██╔══██║
#  ██║██████╔╝██║  ██║██║  ██║██║  ██║
#  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
#  ╔═══════════════════════════════════════════════════════════════════════════╗
#  ║               MEGA BOT – IBRAA TRADEMARK                              ║
#  ║         Keyword Tracker • Moderation • Music • Security               ║
#  ╚═══════════════════════════════════════════════════════════════════════════╝
#  📌 Version: 4.0.0  |  🐍 Python 3.10+  |  🎯 Discord.py 2.3.2
# ══════════════════════════════════════════════════════════════════════════════

# ──── IMPORTS ──────────────────────────────────────────────────────────────────
import discord
from discord.ext import commands
import json
import os
import asyncio
import re
from typing import Optional, List, Dict
from dotenv import load_dotenv

# ──── WEBSERVER (FOR RENDER) ──────────────────────────────────────────────────
from flask import Flask
import threading

# ──── ENVIRONMENT ─────────────────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("❌ TOKEN not found in environment variables.")
PREFIX = os.getenv("PREFIX", "!")

# ══════════════════════════════════════════════════════════════════════════════
#  📦 DATA MANAGER – Persistent JSON Storage
# ══════════════════════════════════════════════════════════════════════════════
DATA_FILE = "data.json"

class DataManager:
    """🧠 Thread‑safe JSON storage for all guild configurations."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._lock = asyncio.Lock()
        self._data = {}
        self._load()

    # ──── PRIVATE METHODS ──────────────────────────────────────────────────────
    def _load(self):
        """Load data from file, or create empty structure."""
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
        """💾 Write data to file under lock."""
        async with self._lock:
            try:
                with open(self.filepath, "w") as f:
                    json.dump(self._data, f, indent=4)
            except IOError as e:
                print(f"❌ Failed to save data: {e}")

    # ──── GUILD DATA ───────────────────────────────────────────────────────────
    def get_guild_data(self, guild_id: int) -> dict:
        """📂 Get or create guild configuration."""
        gid = str(guild_id)
        if gid not in self._data["guilds"]:
            self._data["guilds"][gid] = {
                "keywords": [],
                "log_channel": None,
                "mute_role": None,
                "warns": {},
                "warn_limit": 3,
                "auto_mod": False,
                "filter_words": [],
                "anti_spam": True,
                "raid_mode": False
            }
        return self._data["guilds"][gid]

    # ──── KEYWORD MANAGEMENT ──────────────────────────────────────────────────
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

    # ──── LOG CHANNEL ──────────────────────────────────────────────────────────
    async def set_log_channel(self, guild_id: int, channel_id: Optional[int]):
        data = self.get_guild_data(guild_id)
        data["log_channel"] = channel_id
        await self.save()

    def get_log_channel(self, guild_id: int) -> Optional[int]:
        return self.get_guild_data(guild_id).get("log_channel")

    # ──── MUTE ROLE ────────────────────────────────────────────────────────────
    async def set_mute_role(self, guild_id: int, role_id: Optional[int]):
        data = self.get_guild_data(guild_id)
        data["mute_role"] = role_id
        await self.save()

    def get_mute_role(self, guild_id: int) -> Optional[int]:
        return self.get_guild_data(guild_id).get("mute_role")

    # ──── WARNINGS ─────────────────────────────────────────────────────────────
    async def add_warn(self, guild_id: int, user_id: int, reason: str, moderator_id: int) -> int:
        data = self.get_guild_data(guild_id)
        warns = data["warns"].setdefault(str(user_id), [])
        warn_id = len(warns) + 1
        warns.append({
            "id": warn_id,
            "reason": reason,
            "moderator": moderator_id,
            "timestamp": discord.utils.utcnow().isoformat()
        })
        await self.save()
        return warn_id

    async def remove_warn(self, guild_id: int, user_id: int, warn_id: int) -> bool:
        data = self.get_guild_data(guild_id)
        warns = data["warns"].get(str(user_id), [])
        for i, w in enumerate(warns):
            if w["id"] == warn_id:
                warns.pop(i)
                await self.save()
                return True
        return False

    def get_warns(self, guild_id: int, user_id: int) -> List[dict]:
        data = self.get_guild_data(guild_id)
        return data["warns"].get(str(user_id), []).copy()

    async def set_warn_limit(self, guild_id: int, limit: int):
        data = self.get_guild_data(guild_id)
        data["warn_limit"] = limit
        await self.save()

    def get_warn_limit(self, guild_id: int) -> int:
        return self.get_guild_data(guild_id).get("warn_limit", 3)

    # ──── AUTO-MOD ─────────────────────────────────────────────────────────────
    async def set_auto_mod(self, guild_id: int, enabled: bool):
        data = self.get_guild_data(guild_id)
        data["auto_mod"] = enabled
        await self.save()

    def get_auto_mod(self, guild_id: int) -> bool:
        return self.get_guild_data(guild_id).get("auto_mod", False)

    async def add_filter_word(self, guild_id: int, word: str):
        data = self.get_guild_data(guild_id)
        if word not in data["filter_words"]:
            data["filter_words"].append(word)
            await self.save()
            return True
        return False

    async def remove_filter_word(self, guild_id: int, word: str):
        data = self.get_guild_data(guild_id)
        if word in data["filter_words"]:
            data["filter_words"].remove(word)
            await self.save()
            return True
        return False

    def get_filter_words(self, guild_id: int) -> List[str]:
        return self.get_guild_data(guild_id).get("filter_words", [])

    # ──── RAID MODE ────────────────────────────────────────────────────────────
    async def set_raid_mode(self, guild_id: int, enabled: bool):
        data = self.get_guild_data(guild_id)
        data["raid_mode"] = enabled
        await self.save()

    def get_raid_mode(self, guild_id: int) -> bool:
        return self.get_guild_data(guild_id).get("raid_mode", False)

# ══════════════════════════════════════════════════════════════════════════════
#  🤖 BOT SETUP
# ══════════════════════════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
data_manager = DataManager(DATA_FILE)

# ══════════════════════════════════════════════════════════════════════════════
#  🎵 MUSIC PLAYER – Luna Style
# ══════════════════════════════════════════════════════════════════════════════
import yt_dlp

class MusicPlayer:
    """🎵 Advanced music player with queue, loop, and volume control."""
    
    def __init__(self, bot):
        self.bot = bot
        self.queues: Dict[int, asyncio.Queue] = {}
        self.current: Dict[int, Optional[dict]] = {}
        self.voice_clients: Dict[int, discord.VoiceClient] = {}
        self.loops: Dict[int, bool] = {}
        self.volume: Dict[int, float] = {}

    # ──── CONNECTION ────────────────────────────────────────────────────────────
    async def connect(self, ctx: commands.Context):
        """🔗 Connect to the user's voice channel."""
        if not ctx.author.voice:
            await ctx.send("❌ You're not in a voice channel.")
            return None
        if ctx.guild.voice_client is None:
            vc = await ctx.author.voice.channel.connect()
            self.voice_clients[ctx.guild.id] = vc
            self.queues[ctx.guild.id] = asyncio.Queue()
            self.current[ctx.guild.id] = None
            self.loops[ctx.guild.id] = False
            self.volume[ctx.guild.id] = 1.0
            return vc
        else:
            if ctx.guild.voice_client.channel != ctx.author.voice.channel:
                await ctx.guild.voice_client.move_to(ctx.author.voice.channel)
            return ctx.guild.voice_client

    # ──── STREAM SOURCE ────────────────────────────────────────────────────────
    async def get_source(self, url: str):
        """📡 Extract audio stream from YouTube."""
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return discord.FFmpegPCMAudio(
                    info['url'],
                    before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
                )
        except Exception as e:
            print(f"🎵 Music error: {e}")
            return None

    # ──── QUEUE MANAGEMENT ──────────────────────────────────────────────────────
    async def add_to_queue(self, ctx: commands.Context, url: str):
        """➕ Add a song to the queue."""
        guild_id = ctx.guild.id
        if guild_id not in self.queues:
            await self.connect(ctx)
            if guild_id not in self.queues:
                return False

        ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                song = {
                    'title': info.get('title', 'Unknown'),
                    'url': info.get('webpage_url', url),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', None),
                    'uploader': info.get('uploader', 'Unknown')
                }
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")
            return False

        await self.queues[guild_id].put(song)
        if not self.voice_clients.get(guild_id) or not self.voice_clients[guild_id].is_playing():
            asyncio.create_task(self.play_next(guild_id))
        return True

    # ──── PLAYBACK ──────────────────────────────────────────────────────────────
    async def play_next(self, guild_id: int):
        """▶️ Play the next song in queue."""
        if guild_id not in self.queues:
            return

        if self.loops.get(guild_id, False) and self.current.get(guild_id):
            await self.queues[guild_id].put(self.current[guild_id])

        try:
            song = await asyncio.wait_for(self.queues[guild_id].get(), timeout=60.0)
        except asyncio.TimeoutError:
            vc = self.voice_clients.get(guild_id)
            if vc and vc.is_connected():
                await vc.disconnect()
            self.voice_clients.pop(guild_id, None)
            self.queues.pop(guild_id, None)
            self.current.pop(guild_id, None)
            self.loops.pop(guild_id, None)
            self.volume.pop(guild_id, None)
            return

        self.current[guild_id] = song
        vc = self.voice_clients.get(guild_id)
        if not vc:
            return

        source = await self.get_source(song['url'])
        if source is None:
            await self.play_next(guild_id)
            return

        source.volume = self.volume.get(guild_id, 1.0)
        vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
            self.play_next(guild_id), self.bot.loop
        ))

    # ──── PLAYER CONTROLS ──────────────────────────────────────────────────────
    async def skip(self, ctx: commands.Context):
        """⏭️ Skip the current song."""
        guild_id = ctx.guild.id
        vc = self.voice_clients.get(guild_id)
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("❌ Nothing playing.")

    async def stop(self, ctx: commands.Context):
        """⏹️ Stop playback and clear queue."""
        guild_id = ctx.guild.id
        vc = self.voice_clients.get(guild_id)
        if vc:
            vc.stop()
            self.queues[guild_id] = asyncio.Queue()
            await vc.disconnect()
            self.voice_clients.pop(guild_id, None)
            await ctx.send("⏹️ Stopped and cleared queue.")
        else:
            await ctx.send("❌ Not connected.")

    async def set_volume(self, ctx: commands.Context, vol: int):
        """🔊 Adjust playback volume."""
        if vol < 0 or vol > 200:
            await ctx.send("❌ Volume must be between 0-200.")
            return
        guild_id = ctx.guild.id
        self.volume[guild_id] = vol / 100.0
        vc = self.voice_clients.get(guild_id)
        if vc and vc.is_playing():
            vc.source.volume = self.volume[guild_id]
        await ctx.send(f"🔊 Volume set to {vol}%.")

# ──── INSTANTIATE ──────────────────────────────────────────────────────────────
music_player = MusicPlayer(bot)

# ══════════════════════════════════════════════════════════════════════════════
#  🛡️ SECURITY MANAGER – Anti-Spam & Raid Protection
# ══════════════════════════════════════════════════════════════════════════════
class SecurityManager:
    """🛡️ Monitors messages and joins for suspicious activity."""
    
    def __init__(self):
        self.user_messages: Dict[int, List[float]] = {}
        self.raid_joins: Dict[int, List[float]] = {}

    async def check_spam(self, message: discord.Message) -> bool:
        """🚫 Detect spam (5+ messages in 5 seconds)."""
        user_id = message.author.id
        now = discord.utils.utcnow().timestamp()
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        self.user_messages[user_id] = [t for t in self.user_messages[user_id] if now - t < 5]
        self.user_messages[user_id].append(now)
        return len(self.user_messages[user_id]) > 5

    async def check_raid(self, guild: discord.Guild) -> bool:
        """🚨 Detect raid (5+ joins in 10 seconds)."""
        now = discord.utils.utcnow().timestamp()
        gid = guild.id
        if gid not in self.raid_joins:
            self.raid_joins[gid] = []
        self.raid_joins[gid] = [t for t in self.raid_joins[gid] if now - t < 10]
        return len(self.raid_joins[gid]) > 5

security = SecurityManager()

# ══════════════════════════════════════════════════════════════════════════════
#  📡 EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    """🚀 Bot startup message."""
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print(f"║  ✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("║  🔷 Trademark IBRAA – All rights reserved.")
    print("║  🎯 Mega Bot is ready!")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    await bot.tree.sync()

@bot.event
async def on_message(message: discord.Message):
    """📩 Handle all incoming messages."""
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    guild_id = message.guild.id
    data = data_manager.get_guild_data(guild_id)

    # ──── AUTO-MOD (Filter bad words) ──────────────────────────────────────────
    if data.get("auto_mod", False):
        filter_words = data.get("filter_words", [])
        if filter_words:
            content_lower = message.content.lower()
            for word in filter_words:
                if word in content_lower:
                    try:
                        await message.delete()
                        await message.channel.send(
                            f"🚫 {message.author.mention}, that word is not allowed.",
                            delete_after=5
                        )
                    except discord.Forbidden:
                        pass
                    break

    # ──── ANTI-SPAM ─────────────────────────────────────────────────────────────
    if data.get("anti_spam", True):
        if await security.check_spam(message):
            try:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention}, slow down!",
                    delete_after=3
                )
            except discord.Forbidden:
                pass

    # ──── KEYWORD TRACKER ───────────────────────────────────────────────────────
    keywords = data.get("keywords", [])
    if keywords:
        content_lower = message.content.lower()
        matched = [kw for kw in keywords if kw in content_lower]
        if matched:
            log_channel_id = data.get("log_channel")
            if log_channel_id:
                channel = message.guild.get_channel(log_channel_id)
                if channel:
                    embed = discord.Embed(
                        title="🔍 Keyword Detected",
                        description=f"**{message.author.mention}** said:",
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="Message", value=message.content[:1024], inline=False)
                    embed.add_field(
                        name="Matched Keywords",
                        value=", ".join(f"`{kw}`" for kw in matched),
                        inline=False
                    )
                    embed.add_field(name="Jump", value=f"[Click here]({message.jump_url})", inline=False)
                    embed.set_footer(text=f"#{message.channel.name} • Trademark IBRAA")
                    try:
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        pass

@bot.event
async def on_member_join(member: discord.Member):
    """👤 Track joins for raid detection."""
    guild = member.guild
    now = discord.utils.utcnow().timestamp()
    gid = guild.id
    if gid not in security.raid_joins:
        security.raid_joins[gid] = []
    security.raid_joins[gid].append(now)

    if data_manager.get_raid_mode(guild.id):
        if await security.check_raid(guild):
            everyone = guild.default_role
            try:
                await everyone.edit(permissions=discord.Permissions.none())
                print(f"🚨 RAID DETECTED in {guild.name}! Server locked.")
            except discord.Forbidden:
                pass

# ══════════════════════════════════════════════════════════════════════════════
#  ⌨️ COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

# ──── KEYWORD COMMANDS ────────────────────────────────────────────────────────

@bot.command(name="addkeyword", aliases=["addkw"])
@commands.has_permissions(administrator=True)
async def add_keyword(ctx, *, keyword: str):
    """➕ Add a keyword to track."""
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
    """➖ Remove a tracked keyword."""
    success = await data_manager.remove_keyword(ctx.guild.id, keyword)
    if success:
        await ctx.send(f"✅ Keyword `{keyword}` removed.")
    else:
        await ctx.send(f"❌ Keyword `{keyword}` not found.")

@bot.command(name="listkeywords", aliases=["listkw", "keywords"])
async def list_keywords(ctx):
    """📋 List all tracked keywords."""
    keywords = data_manager.list_keywords(ctx.guild.id)
    if not keywords:
        await ctx.send("📭 No keywords tracked.")
        return
    await ctx.send(f"📋 Tracked keywords ({len(keywords)}):\n" + "\n".join(f"• `{kw}`" for kw in keywords))

@bot.command(name="setlogchannel", aliases=["setlog"])
@commands.has_permissions(administrator=True)
async def set_log_channel(ctx, channel: discord.TextChannel = None):
    """📢 Set the logging channel for alerts."""
    if channel is None:
        await data_manager.set_log_channel(ctx.guild.id, None)
        await ctx.send("🔕 Alerts disabled.")
    else:
        await data_manager.set_log_channel(ctx.guild.id, channel.id)
        await ctx.send(f"📢 Alerts will go to {channel.mention}")

# ──── MODERATION COMMANDS ────────────────────────────────────────────────────

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """👢 Kick a member from the server."""
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 **{member}** kicked. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick that user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """🔨 Ban a member from the server."""
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 **{member}** banned. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban that user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_name: str):
    """🔓 Unban a user by name."""
    async for ban_entry in ctx.guild.bans():
        if ban_entry.user.name == user_name or str(ban_entry.user) == user_name:
            await ctx.guild.unban(ban_entry.user)
            await ctx.send(f"✅ Unbanned {ban_entry.user.mention}")
            return
    await ctx.send(f"❌ User '{user_name}' not found in ban list.")

@bot.command(name="clear", aliases=["purge"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    """🧹 Delete a specified number of messages."""
    if amount < 1 or amount > 1000:
        await ctx.send("❌ Amount must be between 1 and 1000.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Deleted {len(deleted) - 1} messages.", delete_after=5)

@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """🔇 Mute a member."""
    mute_role_id = data_manager.get_mute_role(ctx.guild.id)
    if mute_role_id is None:
        await ctx.send("❌ No mute role set. Use `!setmuterole @role`")
        return
    role = ctx.guild.get_role(mute_role_id)
    if role is None:
        await ctx.send("❌ Mute role not found.")
        return
    try:
        await member.add_roles(role, reason=reason)
        await ctx.send(f"🔇 **{member}** muted. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to mute that user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="unmute")
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    """🔊 Unmute a member."""
    mute_role_id = data_manager.get_mute_role(ctx.guild.id)
    if mute_role_id is None:
        await ctx.send("❌ No mute role set.")
        return
    role = ctx.guild.get_role(mute_role_id)
    if role is None:
        await ctx.send("❌ Mute role not found.")
        return
    try:
        await member.remove_roles(role)
        await ctx.send(f"🔊 **{member}** unmuted.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unmute that user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="setmuterole")
@commands.has_permissions(administrator=True)
async def set_mute_role(ctx, role: discord.Role = None):
    """🔧 Set the mute role for the server."""
    if role is None:
        await data_manager.set_mute_role(ctx.guild.id, None)
        await ctx.send("🔇 Mute role cleared.")
    else:
        await data_manager.set_mute_role(ctx.guild.id, role.id)
        await ctx.send(f"🔇 Mute role set to {role.mention}")

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """⚠️ Warn a member."""
    warn_id = await data_manager.add_warn(ctx.guild.id, member.id, reason, ctx.author.id)
    await ctx.send(f"⚠️ **{member}** warned (ID: {warn_id}). Reason: {reason}")

    warn_limit = data_manager.get_warn_limit(ctx.guild.id)
    if len(data_manager.get_warns(ctx.guild.id, member.id)) >= warn_limit:
        try:
            await member.kick(reason=f"Exceeded warn limit ({warn_limit})")
            await ctx.send(f"🚪 **{member}** kicked for exceeding warn limit.")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to kick.")

@bot.command(name="warns")
async def warns(ctx, member: discord.Member):
    """📋 List all warnings for a member."""
    warns = data_manager.get_warns(ctx.guild.id, member.id)
    if not warns:
        await ctx.send(f"📭 **{member}** has no warnings.")
        return
    embed = discord.Embed(title=f"Warnings for {member}", color=discord.Color.red())
    for w in warns:
        embed.add_field(
            name=f"ID: {w['id']}",
            value=f"Reason: {w['reason']}\nMod: <@{w['moderator']}>\nTime: {w['timestamp']}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="removewarn")
@commands.has_permissions(manage_messages=True)
async def remove_warn(ctx, member: discord.Member, warn_id: int):
    """🗑️ Remove a specific warning."""
    success = await data_manager.remove_warn(ctx.guild.id, member.id, warn_id)
    if success:
        await ctx.send(f"✅ Removed warning #{warn_id} from {member}.")
    else:
        await ctx.send(f"❌ Warning #{warn_id} not found for {member}.")

@bot.command(name="setwarnlimit")
@commands.has_permissions(administrator=True)
async def set_warn_limit(ctx, limit: int):
    """⚙️ Set the warning limit before auto-kick."""
    if limit < 1:
        await ctx.send("❌ Limit must be at least 1.")
        return
    await data_manager.set_warn_limit(ctx.guild.id, limit)
    await ctx.send(f"⚠️ Warn limit set to {limit}.")

# ──── SECURITY COMMANDS ──────────────────────────────────────────────────────

@bot.command(name="automod")
@commands.has_permissions(administrator=True)
async def auto_mod(ctx, state: str):
    """🛡️ Enable/disable auto-mod (bad word filter)."""
    if state.lower() in ["on", "enable", "true"]:
        await data_manager.set_auto_mod(ctx.guild.id, True)
        await ctx.send("🛡️ Auto-mod enabled.")
    elif state.lower() in ["off", "disable", "false"]:
        await data_manager.set_auto_mod(ctx.guild.id, False)
        await ctx.send("🛡️ Auto-mod disabled.")
    else:
        await ctx.send("❌ Use `on` or `off`.")

@bot.command(name="filterword")
@commands.has_permissions(administrator=True)
async def filter_word(ctx, action: str, *, word: str):
    """🔍 Add or remove a filtered word."""
    if action.lower() == "add":
        success = await data_manager.add_filter_word(ctx.guild.id, word.lower())
        if success:
            await ctx.send(f"✅ `{word}` added to filter list.")
        else:
            await ctx.send(f"❌ `{word}` already in filter list.")
    elif action.lower() == "remove":
        success = await data_manager.remove_filter_word(ctx.guild.id, word.lower())
        if success:
            await ctx.send(f"✅ `{word}` removed from filter list.")
        else:
            await ctx.send(f"❌ `{word}` not found in filter list.")
    else:
        await ctx.send("❌ Use `add` or `remove`.")

@bot.command(name="filterlist")
async def filter_list(ctx):
    """📋 List all filtered words."""
    words = data_manager.get_filter_words(ctx.guild.id)
    if not words:
        await ctx.send("📭 No filtered words.")
        return
    await ctx.send(f"📋 Filtered words:\n" + "\n".join(f"• `{w}`" for w in words))

@bot.command(name="raidmode")
@commands.has_permissions(administrator=True)
async def raid_mode(ctx, state: str):
    """🛡️ Enable/disable raid mode (auto-lock on mass joins)."""
    if state.lower() in ["on", "enable", "true"]:
        await data_manager.set_raid_mode(ctx.guild.id, True)
        await ctx.send("🛡️ Raid mode enabled.")
    elif state.lower() in ["off", "disable", "false"]:
        await data_manager.set_raid_mode(ctx.guild.id, False)
        await ctx.send("🛡️ Raid mode disabled.")
    else:
        await ctx.send("❌ Use `on` or `off`.")

@bot.command(name="antispam")
@commands.has_permissions(administrator=True)
async def anti_spam(ctx, state: str):
    """🛡️ Enable/disable anti-spam."""
    data = data_manager.get_guild_data(ctx.guild.id)
    if state.lower() in ["on", "enable", "true"]:
        data["anti_spam"] = True
        await data_manager.save()
        await ctx.send("🛡️ Anti-spam enabled.")
    elif state.lower() in ["off", "disable", "false"]:
        data["anti_spam"] = False
        await data_manager.save()
        await ctx.send("🛡️ Anti-spam disabled.")
    else:
        await ctx.send("❌ Use `on` or `off`.")

@bot.command(name="lockdown")
@commands.has_permissions(administrator=True)
async def lockdown(ctx):
    """🔒 Lock down the server."""
    try:
        everyone = ctx.guild.default_role
        await everyone.edit(permissions=discord.Permissions.none())
        await ctx.send("🔒 Server locked down.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to do that.")

@bot.command(name="unlock")
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    """🔓 Unlock the server."""
    try:
        everyone = ctx.guild.default_role
        await everyone.edit(permissions=discord.Permissions.all())
        await ctx.send("🔓 Server unlocked.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to do that.")

# ──── MUSIC COMMANDS ─────────────────────────────────────────────────────────

@bot.command(name="play", aliases=["p"])
async def play(ctx, *, query: str):
    """🎵 Play a song from YouTube."""
    await music_player.connect(ctx)
    if not re.match(r'https?://', query):
        query = f"ytsearch:{query}"
    success = await music_player.add_to_queue(ctx, query)
    if success:
        await ctx.send("🎵 Added to queue.")

@bot.command(name="skip", aliases=["s"])
async def skip(ctx):
    """⏭️ Skip the current song."""
    await music_player.skip(ctx)

@bot.command(name="stop", aliases=["leave"])
async def stop(ctx):
    """⏹️ Stop playback and leave the voice channel."""
    await music_player.stop(ctx)

@bot.command(name="queue", aliases=["q"])
async def show_queue(ctx):
    """📋 Show the current queue."""
    guild_id = ctx.guild.id
    q = music_player.queues.get(guild_id)
    if q is None or q.empty():
        await ctx.send("📭 Queue is empty.")
        return
    items = []
    for _ in range(min(10, q.qsize())):
        item = await q.get()
        items.append(item)
        await q.put(item)
    if not items:
        await ctx.send("📭 Queue is empty.")
        return
    embed = discord.Embed(title="🎶 Queue", color=discord.Color.blue())
    for i, song in enumerate(items):
        embed.add_field(
            name=f"{i+1}. {song['title']}",
            value=f"by {song['uploader']}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="nowplaying", aliases=["np"])
async def now_playing(ctx):
    """🎵 Show the currently playing song."""
    guild_id = ctx.guild.id
    current = music_player.current.get(guild_id)
    if current is None:
        await ctx.send("❌ Nothing playing.")
        return
    embed = discord.Embed(title="🎵 Now Playing", color=discord.Color.green())
    embed.add_field(name="Title", value=current['title'], inline=False)
    embed.add_field(name="Uploader", value=current['uploader'], inline=False)
    if current.get('thumbnail'):
        embed.set_thumbnail(url=current['thumbnail'])
    await ctx.send(embed=embed)

@bot.command(name="volume", aliases=["vol"])
async def volume(ctx, vol: int = None):
    """🔊 Adjust or view playback volume."""
    if vol is None:
        current_vol = music_player.volume.get(ctx.guild.id, 1.0) * 100
        await ctx.send(f"🔊 Current volume: {int(current_vol)}%")
    else:
        await music_player.set_volume(ctx, vol)

@bot.command(name="loop")
async def loop(ctx):
    """🔁 Toggle loop mode."""
    guild_id = ctx.guild.id
    current = music_player.loops.get(guild_id, False)
    music_player.loops[guild_id] = not current
    await ctx.send(f"🔁 Loop {'enabled' if not current else 'disabled'}.")

# ══════════════════════════════════════════════════════════════════════════════
#  🚨 ERROR HANDLING
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Bad argument: {error}")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"⚠️ Unexpected error: {error}")
        print(f"Error: {error}")

# ══════════════════════════════════════════════════════════════════════════════
#  🌐 KEEP-ALIVE WEB SERVER (FOR RENDER)
# ══════════════════════════════════════════════════════════════════════════════

app = Flask('')

@app.route('/')
def home():
    return "🚀 IBRAA Mega Bot is running!"

def run_web():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
#  🚀 START BOT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid token.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
#  🏁 END OF FILE – IBRAA TRADEMARK
# ══════════════════════════════════════════════════════════════════════════════
