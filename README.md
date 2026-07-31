# IBRAA Mega Bot

A powerful Discord bot with Keyword Tracking, ProBot‑style Moderation, and Luna‑style Music – all in one.

## Features
- 🔍 **Keyword tracking** – alerts when specified words appear.
- 🛡️ **Moderation** – kick, ban, clear, mute, warn, etc.
- 🎵 **Music** – play from YouTube, queue, skip, volume, loop.

## Setup
1. Clone this repo.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set your `TOKEN`.
4. Run: `python main.py`

## Commands (prefix `!`)

### Keyword
- `!addkeyword <word>` – track a keyword.
- `!removekeyword <word>` – stop tracking.
- `!listkeywords` – show tracked keywords.
- `!setlogchannel #channel` – set alert channel.

### Moderation
- `!kick @user [reason]`
- `!ban @user [reason]`
- `!unban username`
- `!clear <amount>`
- `!setmuterole @role`
- `!mute @user [reason]`
- `!unmute @user`
- `!warn @user [reason]`
- `!warns @user`
- `!removewarn @user <warn_id>`

### Music
- `!play <song name or URL>`
- `!skip`
- `!stop`
- `!queue`
- `!nowplaying`
- `!volume [0-200]`
- `!loop`

## Trademark
This project includes **IBRAA** trademarks. All rights reserved.
