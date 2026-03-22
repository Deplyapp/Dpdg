# 🎌 Crunchyroll Checker Bot

A fast, fully automated Telegram bot that checks Crunchyroll accounts from a combo list — with built-in proxies, button-based UI, and real-time progress updates.

## ✨ Features

- 🔌 **Auto-proxies** — 400+ built-in proxies, no setup needed
- ⚡ **10 concurrent threads** for fast checking
- 🎯 **Plan detection** — Fan, Mega Fan, Ultimate Fan, Premium
- 📅 **Expiry & renewal date** extraction
- 🛑 **Cancel button** — stop any check mid-way
- 📂 **Hits file** — sent automatically when checking completes
- 🖱️ **Button-based UI** — fully inline keyboard driven
- 🛡️ **Error handling** — network errors, bad requests, blocked bot, all handled gracefully

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/Deplyapp/Dpdg.git
cd Dpdg
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your bot token
```bash
export BOT_TOKEN=your_telegram_bot_token_here
```

### 4. Run the bot
```bash
python3 crunchyroll_bot.py
```

## 🐳 Docker

```bash
docker build -t crunchyroll-bot .
docker run -e BOT_TOKEN=your_token_here crunchyroll-bot
```

## 📋 Combo Format

Your `.txt` combo file should have one account per line:
```
email@example.com:password123
user@domain.com:mypassword
```

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Open the main menu |
| `/cancel` | Stop the active check |
| `/help` | Show usage instructions |

## 📁 Files

| File | Description |
|------|-------------|
| `crunchyroll_bot.py` | Main bot script |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Docker build config |
| `.gitignore` | Git ignore rules |

## ⚙️ Requirements

- Python 3.11+
- `python-telegram-bot==22.7`
- `aiohttp==3.13.3`

## 🔐 Environment Variables

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Your Telegram bot token from [@BotFather](https://t.me/BotFather) |

---
Made by [@SynaxBotz](https://t.me/SynaxBotz)
