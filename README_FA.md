# Spike Theme Studio

## Files
- `bot.py`: Telegram bot
- `main.py`: conventional entrypoint wrapper for hosts that auto-detect `main.py`
- `requirements.txt`: Python dependencies

## FadeHost environment variables
Set these in the app's environment settings:
- `TELEGRAM_BOT_TOKEN`: the bot token from BotFather (secret; never commit it)
- `OWNER_ID`: your numeric Telegram user ID (example format: digits only)

Do not put your bot token in GitHub files or send it in chat.

## Features
- Inline menu, dark/light mode, four color styles
- Asks for a project name and then a wallpaper photo
- Generates an `.attheme` file using colors sampled from the image
- Generates a Telegram-style illustrative preview PNG
- Sends the original wallpaper as a separate file
- SQLite-based counts for users, themes and errors; owner-only admin panel

## Important limitations
- The preview is an illustration, not a screenshot of the official Telegram app.
- Telegram may ignore or interpret some `.attheme` keys differently depending on its Android version.
- The bot cannot silently set the wallpaper on your phone. Apply the wallpaper yourself in Telegram.
- SQLite data may be lost if the hosting provider resets ephemeral storage.
- This is a functional starter, not a guarantee that every key is supported by every Telegram version. Test the output on your Telegram Android client.

## Run locally
`pip install -r requirements.txt`
Set environment variables, then run `python main.py`.
