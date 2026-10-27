import os
import io
import logging
from PIL import Image
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Telegram Android .attheme colors use RGB hex values without '#'.
def rgb_hex(rgb):
    r, g, b = rgb
    return f"{r:02X}{g:02X}{b:02X}"

def analyze_palette(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = im.convert("RGB")
        im.thumbnail((160, 160))
        # Quantization gives a small palette representative of the wallpaper.
        pal_img = im.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
        palette = pal_img.getpalette()
        colors = pal_img.getcolors() or []
        colors.sort(reverse=True)
        result = []
        for count, idx in colors:
            rgb = tuple(palette[idx * 3: idx * 3 + 3])
            result.append((count, rgb))
        if not result:
            result = [(1, (30, 35, 45))]
        return [rgb for _, rgb in result[:8]]

def luminance(rgb):
    r, g, b = rgb
    return 0.2126*r + 0.7152*g + 0.0722*b

def make_theme(palette, mode="dark"):
    # A starter theme that samples the wallpaper and assigns colors to common Telegram UI keys.
    accent = palette[0] if palette else (70, 130, 220)
    if mode == "dark":
        bg = (20, 22, 28)
        panel = (29, 32, 40)
        text = (238, 240, 245)
        hint = (150, 158, 172)
        incoming = (38, 42, 52)
        outgoing = tuple(max(0, min(255, int(c * 0.72 + a * 0.28))) for c, a in zip(accent, (25, 125, 90)))
    else:
        bg = (248, 249, 252)
        panel = (255, 255, 255)
        text = (30, 34, 42)
        hint = (110, 118, 130)
        incoming = (239, 242, 247)
        outgoing = tuple(max(0, min(255, int(c * 0.35 + a * 0.65))) for c, a in zip(accent, (190, 225, 200)))

    # Prefer readable contrast if the sampled accent is too light/dark.
    if luminance(accent) > 220:
        accent = tuple(int(c * 0.72) for c in accent)
    if luminance(accent) < 45:
        accent = tuple(min(255, int(c + 70)) for c in accent)

    values = {
        "windowBackgroundWhite": bg,
        "windowBackgroundGray": panel,
        "actionBarDefault": panel,
        "actionBarDefaultIcon": text,
        "actionBarDefaultTitle": text,
        "actionBarDefaultSubtitle": hint,
        "windowBackgroundWhiteBlackText": text,
        "windowBackgroundWhiteGrayText": hint,
        "windowBackgroundWhiteBlueText": accent,
        "windowBackgroundWhiteLinkText": accent,
        "chat_inBubble": incoming,
        "chat_outBubble": outgoing,
        "chat_messageTextIn": text,
        "chat_messageTextOut": (255, 255, 255) if luminance(outgoing) < 155 else (25, 28, 34),
        "chat_inTimeText": hint,
        "chat_outTimeText": (245, 245, 245),
        "chat_status": accent,
        "chat_outSentCheck": accent,
        "chat_outSentCheckSelected": accent,
        "chats_menuTopBackground": panel,
        "chats_menuTopShadow": (0, 0, 0),
        "divider": (65, 70, 80) if mode == "dark" else (220, 224, 230),
        "listSelectorSDK21": accent,
        "checkbox": accent,
        "radioBackground": accent,
        "switchTrack": hint,
        "switchTrackChecked": accent,
        "switchThumb": (245, 245, 245),
        "switchThumbChecked": (255, 255, 255),
        "avatar_backgroundBlue": accent,
        "avatar_text": (255, 255, 255),
    }
    return "\n".join(f"{key}={rgb_hex(rgb)}" for key, rgb in values.items()) + "\n"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! عکس والپیپر رو بفرست تا از رنگ‌هاش یک تم پایهٔ تلگرام اندروید (.attheme) بسازم.\n\n"
        "برای حالت تیره: /dark\nبرای حالت روشن: /light\n"
        "نکته: این نسخه تم رنگی می‌سازد؛ والپیپر را خودش روی تلگرام تنظیم نمی‌کند."
    )

async def dark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "dark"
    await update.message.reply_text("حالت تیره انتخاب شد. حالا عکس والپیپر رو بفرست.")

async def light(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "light"
    await update.message.reply_text("حالت روشن انتخاب شد. حالا عکس والپیپر رو بفرست.")

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.photo:
        return
    await message.reply_text("دارم رنگ‌های عکس رو بررسی می‌کنم...")
    try:
        photo_file = await message.photo[-1].get_file()
        buf = io.BytesIO()
        await photo_file.download_to_memory(out=buf)
        palette = analyze_palette(buf.getvalue())
        mode = context.user_data.get("mode", "dark")
        theme_data = make_theme(palette, mode).encode("utf-8")
        theme_name = "SpikeThemeDark.attheme" if mode == "dark" else "SpikeThemeLight.attheme"
        await message.reply_document(
            document=io.BytesIO(theme_data),
            filename=theme_name,
            caption="تم پایه آماده شد. فایل رو در تلگرام اندروید باز کن و گزینهٔ اعمال تم رو بزن."
        )
    except Exception:
        log.exception("Failed to create theme")
        await message.reply_text("ساخت تم ناموفق شد. لطفاً یک عکس JPG یا PNG دیگه بفرست.")

def main():
    if not TOKEN:
        raise RuntimeError(
            "متغیر TELEGRAM_BOT_TOKEN تنظیم نشده. توکن ربات را در Environment Variables هاست وارد کن."
        )
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dark", dark))
    app.add_handler(CommandHandler("light", light))
    app.add_handler(MessageHandler(filters.PHOTO, photo))
    app.run_polling()

if __name__ == "__main__":
    main()
