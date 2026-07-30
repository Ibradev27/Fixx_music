# Keyword Tracker Bot – Trademark IBRAA

A Discord bot that monitors messages for specific keywords and sends alerts to a configured channel.

## Features
- Add/remove keywords (admin only)
- List all tracked keywords
- Set a logging channel for alerts
- Case‑insensitive matching
- Persistent JSON storage

## Setup
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `config.json.example` to `config.json` and insert your bot token.
4. Run: `python main.py`

## Commands
- `!addkeyword <keyword>` – add a keyword
- `!removekeyword <keyword>` – remove a keyword
- `!listkeywords` – show tracked keywords
- `!setlogchannel #channel` – set alert channel (or disable with no channel)

## Trademark
This project includes **IBRAA** trademarks. All rights reserved.
