import io
import os
import re
import logging
from collections import Counter

from PIL import Image, ImageOps, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("spike-theme-bot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_ID = os.getenv("OWNER_ID", "").strip()


def safe_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value or "SpikeTheme").strip("_")
    return (value[:40] or "SpikeTheme")


def blend(a, b, amount):
    amount = max(0.0, min(1.0, amount))
    return tuple(round(a[i] * (1 - amount) + b[i] * amount) for i in range(3))


def luminance(rgb):
    r, g, b = [v / 255 for v in rgb]
    def f(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast_text(rgb):
    return (20, 22, 28) if luminance(rgb) > 0.45 else (245, 247, 250)


def normalized_image(raw: bytes, max_side=1920):
    image = Image.open(io.BytesIO(raw))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=92, optimize=True)
    return image, out.getvalue()


def analyze_palette(image):
    sample = image.copy()
    sample.thumbnail((180, 180), Image.Resampling.LANCZOS)
    quantized = sample.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    counts = quantized.getcolors() or []
    colors = []
    for count, index in sorted(counts, reverse=True):
        start = index * 3
        if start + 2 < len(palette):
            rgb = tuple(palette[start:start + 3])
            if max(rgb) - min(rgb) < 8:
                rgb = tuple(max(0, min(255, int(v))) for v in rgb)
            colors.append((rgb, count))
    colors.sort(key=lambda item: item[1], reverse=True)
    unique = []
    for color, _ in colors:
        if all(sum((color[i] - other[i]) ** 2 for i in range(3)) > 22**2 for other in unique):
            unique.append(color)
    return unique[:6] or [(80, 100, 150)]


def build_colors(palette, mode="dark"):
    accent = palette[0]
    if len(palette) > 1:
        accent2 = palette[1]
    else:
        accent2 = blend(accent, (255, 255, 255), 0.35)

    if mode == "light":
        bg = blend(palette[-1], (255, 255, 255), 0.82)
        panel = blend(bg, (255, 255, 255), 0.45)
        text = (27, 30, 36)
        hint = (105, 110, 120)
        divider = blend(bg, text, 0.13)
        bubble_in = blend(bg, accent, 0.10)
        bubble_out = blend(accent, (255, 255, 255), 0.12)
    else:
        bg = blend(palette[-1], (8, 10, 16), 0.82)
        panel = blend(bg, (255, 255, 255), 0.055)
        text = (238, 240, 245)
        hint = (150, 157, 170)
        divider = blend(bg, (255, 255, 255), 0.12)
        bubble_in = blend(panel, accent2, 0.18)
        bubble_out = blend(accent, (10, 12, 18), 0.18)

    def hex_color(rgb):
        return "#" + "".join(f"{max(0, min(255, int(c))):02X}" for c in rgb)

    # Telegram Android .attheme color keys. Exact coverage varies by Telegram version.
    colors = {
        "windowBackgroundWhite": bg,
        "windowBackgroundGray": panel,
        "actionBarDefault": panel,
        "actionBarDefaultIcon": text,
        "actionBarDefaultTitle": text,
        "actionBarDefaultSubtitle": hint,
        "actionBarDefaultSelector": blend(panel, accent, 0.18),
        "actionBarDefaultSearch": text,
        "actionBarDefaultSearchPlaceholder": hint,
        "actionBarActionModeDefault": panel,
        "actionBarActionModeDefaultIcon": text,
        "actionBarActionModeDefaultTop": accent,
        "actionBarActionModeDefaultSelector": blend(panel, accent, 0.2),
        "avatar_text": contrast_text(accent),
        "chats_name": text,
        "chats_nameMessage": hint,
        "chats_message": hint,
        "chats_date": hint,
        "chats_pinnedIcon": accent,
        "chats_sentCheck": accent,
        "chats_sentCheckRead": accent2,
        "chats_unreadCounter": accent,
        "chats_unreadCounterText": contrast_text(accent),
        "chats_onlineCircle": (55, 190, 105),
        "chats_tabletSelectedOverlay": blend(panel, accent, 0.22),
        "chat_messagePanelBackground": panel,
        "chat_messagePanelText": text,
        "chat_messagePanelHint": hint,
        "chat_fieldOverlayText": text,
        "chat_fieldOverlayTextHint": hint,
        "chat_inBubble": bubble_in,
        "chat_inBubbleSelected": blend(bubble_in, accent, 0.18),
        "chat_outBubble": bubble_out,
        "chat_outBubbleSelected": blend(bubble_out, accent2, 0.18),
        "chat_messageTextIn": text,
        "chat_messageTextOut": contrast_text(bubble_out),
        "chat_messageLinkIn": accent2,
        "chat_messageLinkOut": contrast_text(bubble_out),
        "chat_inTimeText": hint,
        "chat_outTimeText": blend(contrast_text(bubble_out), bubble_out, 0.28),
        "chat_inReplyLine": accent2,
        "chat_outReplyLine": contrast_text(bubble_out),
        "chat_inReplyNameText": accent2,
        "chat_outReplyNameText": contrast_text(bubble_out),
        "chat_inReplyMessageText": text,
        "chat_outReplyMessageText": contrast_text(bubble_out),
        "chat_inReplyMediaMessageText": hint,
        "chat_outReplyMediaMessageText": contrast_text(bubble_out),
        "chat_inSentClock": hint,
        "chat_outSentCheck": contrast_text(bubble_out),
        "chat_outSentCheckRead": contrast_text(bubble_out),
        "chat_inViews": hint,
        "chat_outViews": contrast_text(bubble_out),
        "chat_inMenu": hint,
        "chat_outMenu": contrast_text(bubble_out),
        "chat_wallpaper": bg,
        "chat_serviceBackground": blend(panel, accent, 0.2),
        "chat_serviceText": text,
        "chat_serviceLink": accent2,
        "chat_dateText": text,
        "chat_date": blend(panel, accent, 0.2),
        "chat_emojiPanelBackground": panel,
        "chat_emojiPanelIcon": hint,
        "chat_emojiPanelIconSelected": accent,
        "chat_emojiPanelStickerPackSelector": accent,
        "chat_attachMessage": accent,
        "chat_attachMessageText": contrast_text(accent),
        "chat_recordedVoiceBackground": accent,
        "chat_recordedVoiceDot": (235, 65, 80),
        "chat_recordedVoicePlayPause": contrast_text(accent),
        "chat_recordedVoiceProgress": contrast_text(accent),
        "chat_recordedVoiceSeekbar": contrast_text(accent),
        "chat_recordedVoiceSeekbarFill": accent2,
        "chat_recordedVoiceTime": hint,
        "chat_inFileBackground": blend(panel, accent, 0.15),
        "chat_outFileBackground": blend(bubble_out, accent2, 0.12),
        "chat_inFileNameText": text,
        "chat_outFileNameText": contrast_text(bubble_out),
        "chat_inFileInfoText": hint,
        "chat_outFileInfoText": contrast_text(bubble_out),
        "chat_inFileProgress": accent,
        "chat_outFileProgress": contrast_text(bubble_out),
        "chat_inFileProgressSelected": accent2,
        "chat_outFileProgressSelected": contrast_text(bubble_out),
        "chat_inFileIcon": accent,
        "chat_outFileIcon": contrast_text(bubble_out),
        "chat_inFileIconSelected": accent2,
        "chat_outFileIconSelected": contrast_text(bubble_out),
        "chat_inLoader": accent,
        "chat_outLoader": contrast_text(bubble_out),
        "chat_inLoaderPhoto": text,
        "chat_outLoaderPhoto": contrast_text(bubble_out),
        "chat_inLoaderPhotoIcon": text,
        "chat_outLoaderPhotoIcon": contrast_text(bubble_out),
        "chat_inBubbleShadow": (0, 0, 0),
        "chat_outBubbleShadow": (0, 0, 0),
        "chat_inForwardedNameText": accent2,
        "chat_outForwardedNameText": contrast_text(bubble_out),
        "chat_inViaBotNameText": accent2,
        "chat_outViaBotNameText": contrast_text(bubble_out),
        "chat_inAdminText": accent2,
        "chat_outAdminText": contrast_text(bubble_out),
        "chat_inPsaNameText": accent2,
        "chat_outPsaNameText": contrast_text(bubble_out),
        "chat_inReplyMediaMessageSelectedText": text,
        "chat_outReplyMediaMessageSelectedText": contrast_text(bubble_out),
        "chat_inTextSelectionHighlight": blend(accent, bg, 0.45),
        "chat_outTextSelectionHighlight": blend(accent2, bubble_out, 0.45),
        "dialogBackground": panel,
        "dialogTextBlack": text,
        "dialogTextGray": hint,
        "dialogButton": accent,
        "dialogButtonSelector": blend(panel, accent, 0.18),
        "dialogIcon": hint,
        "windowBackgroundWhiteBlackText": text,
        "windowBackgroundWhiteGrayText": hint,
        "windowBackgroundWhiteBlueText": accent,
        "windowBackgroundWhiteLinkText": accent2,
        "windowBackgroundWhiteHintText": hint,
        "windowBackgroundWhiteInputField": divider,
        "windowBackgroundWhiteInputFieldActivated": accent,
        "checkbox": accent,
        "checkboxCheck": contrast_text(accent),
        "radioBackground": panel,
        "radioBackgroundChecked": accent,
        "switchTrack": divider,
        "switchTrackChecked": blend(accent, bg, 0.25),
        "switchTrackCheckedThumb": accent,
        "switchTrackThumb": hint,
        "progressCircle": accent,
        "featuredStickers_addedIcon": accent,
        "stickers_menu": hint,
        "location_sendLocationBackground": accent,
        "location_sendLocationIcon": contrast_text(accent),
        "profile_actionIcon": accent,
        "profile_actionBackground": panel,
        "profile_verifiedBackground": accent,
        "profile_verifiedCheck": contrast_text(accent),
        "stories_circle1": accent,
        "stories_circle2": accent2,
        "stories_circle3": blend(accent, accent2, 0.5),
        "windowBackgroundWhiteBlueHeader": accent,
        "listSelectorSDK21": blend(panel, accent, 0.18),
        "divider": divider,
        "chat_goDownButton": panel,
        "chat_goDownButtonIcon": text,
    }
    return {key: hex_color(value) for key, value in colors.items()}


def make_attheme(colors, wallpaper_bytes):
    # Telegram's theme format uses WPS/WPE markers for embedded wallpaper data.
    # Telegram Android version support for embedded wallpapers can vary.
    lines = [f"{key}={value}" for key, value in colors.items()]
    return ("\n".join(lines) + "\nWPS\n").encode("utf-8") + wallpaper_bytes + b"\nWPE\n"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🎨 والپیپرت رو به‌صورت عکس بفرست.\n"
        "رنگ‌های تم از روی همون عکس ساخته می‌شن و فایل ‎.attheme‎ رو می‌فرستم."
    )


async def got_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.photo:
        return
    status = await message.reply_text("⏳ دارم رنگ‌های والپیپر رو تحلیل می‌کنم و فایل تم رو می‌سازم…")
    try:
        photo = message.photo[-1]
        tg_file = await context.bot.get_file(photo.file_id)
        raw = bytes(await tg_file.download_as_bytearray())
        wallpaper, wallpaper_jpeg = normalized_image(raw)
        palette = analyze_palette(wallpaper)
        mode = "dark"
        colors = build_colors(palette, mode)
        attheme = make_attheme(colors, wallpaper_jpeg)
        filename = safe_name("SpikeTheme")
        await message.reply_document(
            document=io.BytesIO(attheme),
            filename=f"{filename}.attheme",
            caption=(
                "تم ساخته شد.\n"
                "والپیپر داخل فایل قرار داده شده؛ پشتیبانی از والپیپر تعبیه‌شده "
                "ممکنه بسته به نسخهٔ تلگرام فرق کنه."
            ),
        )
    except Exception:
        log.exception("Theme generation failed")
        await message.reply_text("ساخت تم خطا داد. یه عکس معمولی با فرمت JPG یا PNG بفرست.")
    finally:
        try:
            await status.delete()
        except Exception:
            pass


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled bot error", exc_info=context.error)


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is missing")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    # Photos are handled directly; no menu, project name, or style-selection steps.
    app.add_handler(MessageHandler(filters.PHOTO, got_photo))
    app.add_error_handler(on_error)
    log.info("Spike Theme Studio starting; owner configured=%s", bool(OWNER_ID))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
