# ========================================================
# Trademark IBRAA – All rights reserved.
# This bot is protected under IBRAA intellectual property.
# ========================================================

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import re
from typing import Optional, List, Dict
import yt_dlp
from dotenv import load_dotenv

# ---------- ENVIRONMENT ----------
load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN not found in environment variables.")
PREFIX = os.getenv("PREFIX", "!")

# ---------- DATA MANAGER ----------
DATA_FILE = "data.json"

class DataManager:
    """Thread‑safe JSON storage for guild data."""
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
                "log_channel": None,
                "mute_role": None,
                "warns": {}
            }
        return self._data["guilds"][gid]

    # ---------- KEYWORD METHODS ----------
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

    # ---------- LOG CHANNEL ----------
    async def set_log_channel(self, guild_id: int, channel_id: Optional[int]):
        data = self.get_guild_data(guild_id)
        data["log_channel"] = channel_id
        await self.save()

    def get_log_channel(self, guild_id: int) -> Optional[int]:
        return self.get_guild_data(guild_id).get("log_channel")

    # ---------- MUTE ROLE ----------
    async def set_mute_role(self, guild_id: int, role_id: Optional[int]):
        data = self.get_guild_data(guild_id)
        data["mute_role"] = role_id
        await self.save()

    def get_mute_role(self, guild_id: int) -> Optional[int]:
        return self.get_guild_data(guild_id).get("mute_role")

    # ---------- WARNINGS ----------
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

# ---------- BOT SETUP ----------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True          # for warnings / mod actions
intents.voice_states = True     # for music
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
data_manager = DataManager(DATA_FILE)

# ---------- MUSIC PLAYER ----------
class MusicPlayer:
    """Per‑guild music player."""
    def __init__(self, bot):
        self.bot = bot
        self.queues: Dict[int, asyncio.Queue] = {}
        self.current: Dict[int, Optional[dict]] = {}
        self.voice_clients: Dict[int, discord.VoiceClient] = {}
        self.loops: Dict[int, bool] = {}
        self.volume: Dict[int, float] = {}

    async def get_voice_client(self, guild_id: int) -> Optional[discord.VoiceClient]:
        return self.voice_clients.get(guild_id)

    async def connect(self, ctx: commands.Context):
        if ctx.author.voice is None:
            await ctx.send("❌ You are not in a voice channel.")
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

    async def play_next(self, guild_id: int):
        if guild_id not in self.queues:
            return
        queue = self.queues[guild_id]
        if self.loops.get(guild_id, False) and self.current.get(guild_id):
            # Re-add current to front
            await queue.put(self.current[guild_id])
        try:
            next_song = await asyncio.wait_for(queue.get(), timeout=60.0)
        except asyncio.TimeoutError:
            # Disconnect after 60s of empty queue
            vc = self.voice_clients.get(guild_id)
            if vc and vc.is_connected():
                await vc.disconnect()
            self.voice_clients.pop(guild_id, None)
            self.queues.pop(guild_id, None)
            self.current.pop(guild_id, None)
            self.loops.pop(guild_id, None)
            self.volume.pop(guild_id, None)
            return

        self.current[guild_id] = next_song
        vc = self.voice_clients.get(guild_id)
        if not vc:
            return
        source = await self.get_source(next_song['url'])
        if source is None:
            await self.play_next(guild_id)
            return
        source.volume = self.volume.get(guild_id, 1.0)
        vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(guild_id), self.bot.loop))

    async def get_source(self, url: str):
        """Extract audio stream with yt-dlp."""
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
                url2 = info['url']
                return discord.FFmpegPCMAudio(url2, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")
        except Exception as e:
            print(f"Error getting source: {e}")
            return None

    async def add_to_queue(self, ctx: commands.Context, url: str):
        guild_id = ctx.guild.id
        if guild_id not in self.queues:
            await self.connect(ctx)
            if guild_id not in self.queues:
                return False
        # Extract info
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
            await ctx.send(f"❌ Could not fetch song: {e}")
            return False

        await self.queues[guild_id].put(song)
        # If not playing, start
        if not self.voice_clients.get(guild_id, None) or not self.voice_clients[guild_id].is_playing():
            asyncio.create_task(self.play_next(guild_id))
        return True

    async def skip(self, ctx: commands.Context):
        guild_id = ctx.guild.id
        vc = self.voice_clients.get(guild_id)
        if vc and vc.is_playing():
            vc.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    async def stop(self, ctx: commands.Context):
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
        if vol < 0 or vol > 200:
            await ctx.send("❌ Volume must be between 0 and 200.")
            return
        guild_id = ctx.guild.id
        self.volume[guild_id] = vol / 100.0
        vc = self.voice_clients.get(guild_id)
        if vc and vc.is_playing():
            vc.source.volume = self.volume[guild_id]
        await ctx.send(f"🔊 Volume set to {vol}%.")

# ---------- BOT EVENTS ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"🔷 Trademark IBRAA – All rights reserved.")
    await bot.tree.sync()  # Sync slash commands (if any)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    # Keyword tracking
    keywords = data_manager.list_keywords(message.guild.id)
    if keywords:
        content_lower = message.content.lower()
        matched = [kw for kw in keywords if kw in content_lower]
        if matched:
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
                    embed.set_footer(text=f"#{message.channel.name} • Trademark IBRAA")
                    try:
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        pass

# ---------- COMMANDS ----------
# ----- Keyword commands -----
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
        await ctx.send("📭 No keywords tracked.")
        return
    await ctx.send(f"📋 Tracked keywords ({len(keywords)}):\n" + "\n".join(f"• `{kw}`" for kw in keywords))

@bot.command(name="setlogchannel", aliases=["setlog"])
@commands.has_permissions(administrator=True)
async def set_log_channel(ctx, channel: discord.TextChannel = None):
    if channel is None:
        await data_manager.set_log_channel(ctx.guild.id, None)
        await ctx.send("🔕 Alerts disabled.")
    else:
        await data_manager.set_log_channel(ctx.guild.id, channel.id)
        await ctx.send(f"📢 Alerts will go to {channel.mention}")

# ----- Moderation commands (ProBot style) -----
@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 **{member}** was kicked. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick that user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 **{member}** was banned. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban that user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_name: str):
    async for ban_entry in ctx.guild.bans():
        if ban_entry.user.name == user_name or str(ban_entry.user) == user_name:
            await ctx.guild.unban(ban_entry.user)
            await ctx.send(f"✅ Unbanned {ban_entry.user.mention}")
            return
    await ctx.send(f"❌ User '{user_name}' not found in ban list.")

@bot.command(name="clear", aliases=["purge"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount < 1:
        await ctx.send("❌ Amount must be at least 1.")
        return
    if amount > 1000:
        await ctx.send("❌ Cannot delete more than 1000 messages at once.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Deleted {len(deleted) - 1} messages.", delete_after=5)

@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    mute_role_id = data_manager.get_mute_role(ctx.guild.id)
    if mute_role_id is None:
        await ctx.send("❌ No mute role set. Use `!setmuterole @role`")
        return
    role = ctx.guild.get_role(mute_role_id)
    if role is None:
        await ctx.send("❌ Mute role not found. Reset it with `!setmuterole`")
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
    if role is None:
        await data_manager.set_mute_role(ctx.guild.id, None)
        await ctx.send("🔇 Mute role cleared.")
    else:
        await data_manager.set_mute_role(ctx.guild.id, role.id)
        await ctx.send(f"🔇 Mute role set to {role.mention}")

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    warn_id = await data_manager.add_warn(ctx.guild.id, member.id, reason, ctx.author.id)
    await ctx.send(f"⚠️ **{member}** warned (ID: {warn_id}). Reason: {reason}")

@bot.command(name="warns")
async def warns(ctx, member: discord.Member):
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
    success = await data_manager.remove_warn(ctx.guild.id, member.id, warn_id)
    if success:
        await ctx.send(f"✅ Removed warning #{warn_id} from {member}.")
    else:
        await ctx.send(f"❌ Warning #{warn_id} not found for {member}.")

# ----- Music commands (Luna style) -----
music_player = MusicPlayer(bot)

@bot.command(name="play", aliases=["p"])
async def play(ctx, *, query: str):
    """Play a song from YouTube."""
    vc = await music_player.connect(ctx)
    if vc is None:
        return
    # If query is a URL, use as is; else search
    if not re.match(r'https?://', query):
        query = f"ytsearch:{query}"
    success = await music_player.add_to_queue(ctx, query)
    if success:
        await ctx.send(f"🎵 Added to queue.")

@bot.command(name="skip", aliases=["next"])
async def skip(ctx):
    await music_player.skip(ctx)

@bot.command(name="stop", aliases=["disconnect", "leave"])
async def stop(ctx):
    await music_player.stop(ctx)

@bot.command(name="queue", aliases=["q"])
async def show_queue(ctx):
    guild_id = ctx.guild.id
    q = music_player.queues.get(guild_id)
    if q is None or q.empty():
        await ctx.send("📭 Queue is empty.")
        return
    # Get up to 10 items
    items = []
    for _ in range(min(10, q.qsize())):
        item = await q.get()
        items.append(item)
        await q.put(item)  # put back
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
    if vol is None:
        current_vol = music_player.volume.get(ctx.guild.id, 1.0) * 100
        await ctx.send(f"🔊 Current volume: {int(current_vol)}%")
    else:
        await music_player.set_volume(ctx, vol)

@bot.command(name="loop")
async def loop(ctx):
    guild_id = ctx.guild.id
    current = music_player.loops.get(guild_id, False)
    music_player.loops[guild_id] = not current
    await ctx.send(f"🔁 Loop {'enabled' if not current else 'disabled'}.")

# ---------- ERROR HANDLING ----------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Bad argument: {error}")
    elif isinstance(error, commands.CommandNotFound):
        pass  # ignore
    else:
        await ctx.send(f"⚠️ Unexpected error: {error}")
        print(f"Error: {error}")

# ---------- KEEP-ALIVE WEB SERVER (for Render etc.) ----------
# Optional: uncomment if you want to keep the bot alive on web hosts
# from flask import Flask
# import threading
# app = Flask('')
# @app.route('/')
# def home():
#     return "IBRAA Bot is running!"
# def run_web():
#     app.run(host='0.0.0.0', port=8080)
# threading.Thread(target=run_web, daemon=True).start()

# ---------- START BOT ----------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid token.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
