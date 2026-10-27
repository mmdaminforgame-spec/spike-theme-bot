# Spike Theme Bot

## What it does
- Receives a wallpaper photo in Telegram.
- Samples the image's colors and creates a basic Android Telegram `.attheme` file.
- `/dark` selects a dark palette and `/light` selects a light palette.

This is a starter bot, not a full clone of any existing theme bot. Telegram theme keys can vary by app version. It creates a color theme only; it does not automatically set the wallpaper.

## Hosting setup
1. Set environment variable `TELEGRAM_BOT_TOKEN` to your BotFather token. Do not put the token in this ZIP or share it in chat.
2. Runtime: Python 3.13.
3. Start command: `python bot.py`
4. Install dependencies from `requirements.txt`.

## Local run
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="YOUR_TOKEN"
python bot.py
```
