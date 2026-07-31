# ========================================================
# Trademark IBRAA – All rights reserved.
# ========================================================

import discord
from discord.ext import commands
import json
import os
import asyncio
from typing import Optional, List
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

    async def set_mute_role(self, guild_id: int, role_id: Optional[int]):
        data = self.get_guild_data(guild_id)
        data["mute_role"] = role_id
        await self.save()

    def get_mute_role(self, guild_id: int) -> Optional[int]:
        return self.get_guild_data(guild_id).get("mute_role")

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
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
data_manager = DataManager(DATA_FILE)

# ---------- BOT EVENTS ----------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"🔷 Trademark IBRAA – All rights reserved.")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    await bot.process_commands(message)

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
        await ctx.send(f" Keyword `{keyword}` removed.")
    else:
        await ctx.send(f" Keyword `{keyword}` not found.")

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

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 **{member}** دەرکرا لە سێرڤەر. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send(" توانام نییە ئەم کەسە دەر بکەم .")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 **{member}** was banned. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send(" نـاتوانم ئەم کـەسـە باند بـکەم.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_name: str):
    async for ban_entry in ctx.guild.bans():
        if ban_entry.user.name == user_name or str(ban_entry.user) == user_name:
            await ctx.guild.unban(ban_entry.user)
            await ctx.send(f"✅ باند لابرا {ban_entry.user.mention}")
            return
    await ctx.send(f" بەڕێز '{user_name}' نەدۆزرایەوە لە لیستی باندکراوەکان.")

@bot.command(name="clear", aliases=["purge"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount < 1:
        await ctx.send(" Amount must be at least 1.")
        return
    if amount > 1000:
        await ctx.send(" بەیەک جار ناتوانی لە هەزار نامە زیاترڕەشکەیتەوو.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Deleted {len(deleted) - 1} messages.", delete_after=5)

@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    mute_role_id = data_manager.get_mute_role(ctx.guild.id)
    if mute_role_id is None:
        await ctx.send(" No mute role set. Use `!setmuterole @role`")
        return
    role = ctx.guild.get_role(mute_role_id)
    if role is None:
        await ctx.send(" Mute role not found. Reset it with `!setmuterole`")
        return
    try:
        await member.add_roles(role, reason=reason)
        await ctx.send(f"🔇 **{member}** muted. Reason: {reason}")
    except discord.Forbidden:
        await ctx.send(" توانام نییە ئەم کەسە باند بکەم.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="unmute")
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    mute_role_id = data_manager.get_mute_role(ctx.guild.id)
    if mute_role_id is None:
        await ctx.send(" No mute role set.")
        return
    role = ctx.guild.get_role(mute_role_id)
    if role is None:
        await ctx.send(" Mute role not found.")
        return
    try:
        await member.remove_roles(role)
        await ctx.send(f"🔊 **{member}** unmuted.")
    except discord.Forbidden:
        await ctx.send(" ناتوانم میوتی ئەم کەسە لابدەم.")
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
    await ctx.send(f"⚠️ **{member}** ئاگادارکرایتەوە وریابە  (ID: {warn_id}). Reason: {reason}")

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
        await ctx.send(f"ئاگادار کردنەوە لادرا #{warn_id} لەسەر {member}.")
    else:
        await ctx.send(f"❌ ئاگادارکردنەوە #{warn_id} نەدۆزرایەوە لەسەر {member}.")

# ---------- ERROR HANDLING ----------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(" تۆ توانات نییە ئەم کۆماندە بەکاربێنیت.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Bad argument: {error}")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"⚠️ Unexpected error: {error}")
        print(f"Error: {error}")

# ---------- START BOT ----------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid token.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
