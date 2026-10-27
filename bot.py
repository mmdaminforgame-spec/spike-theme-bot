import io
import logging
import os
import colorsys
from collections import Counter

from PIL import Image, ImageOps, ImageEnhance
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("spike-theme-bot")

STYLES = {
    "neon": {"name": "نئونی", "sat": 1.30, "bright": 1.04, "accent": "#00F5FF", "second": "#FF2BD6"},
    "anime": {"name": "انیمه‌ای", "sat": 1.18, "bright": 1.08, "accent": "#A855F7", "second": "#FF6B9D"},
    "cyber": {"name": "سایبرپانک", "sat": 1.35, "bright": 0.92, "accent": "#00F0A8", "second": "#FF3864"},
    "ice": {"name": "آبی یخی", "sat": 0.95, "bright": 1.12, "accent": "#67E8F9", "second": "#818CF8"},
    "purple": {"name": "بنفش الکتریکی", "sat": 1.20, "bright": 0.98, "accent": "#C084FC", "second": "#7C3AED"},
    "red": {"name": "قرمز تیره", "sat": 1.12, "bright": 0.90, "accent": "#FB3640", "second": "#FF7A45"},
    "lux": {"name": "دارک لوکس", "sat": 0.90, "bright": 0.88, "accent": "#D6B4FC", "second": "#8B9BB4"},
    "wall": {"name": "هماهنگ با والپیپر", "sat": 1.05, "bright": 1.00, "accent": None, "second": None},
}

# Common Telegram Android .attheme color keys. Unknown keys are generally ignored by Telegram.
BASE_COLORS = {
    "windowBackgroundWhite": "#11131A",
    "windowBackgroundWhiteBlackText": "#F4F5FA",
    "windowBackgroundWhiteGrayText": "#A8ADBD",
    "windowBackgroundWhiteGrayText2": "#7D8496",
    "windowBackgroundWhiteGrayText3": "#6C7385",
    "windowBackgroundWhiteGrayText4": "#555D70",
    "windowBackgroundWhiteBlueText": "#7C8CFF",
    "windowBackgroundWhiteLinkText": "#7C8CFF",
    "windowBackgroundWhiteLinkSelection": "#7C8CFF",
    "windowBackgroundGray": "#0B0D12",
    "actionBarDefault": "#151824",
    "actionBarDefaultIcon": "#F4F5FA",
    "actionBarDefaultTitle": "#F4F5FA",
    "actionBarDefaultSubtitle": "#A8ADBD",
    "actionBarDefaultSelector": "#30354A",
    "actionBarDefaultSearch": "#F4F5FA",
    "actionBarDefaultSearchPlaceholder": "#A8ADBD",
    "actionBarActionModeDefault": "#202438",
    "actionBarActionModeDefaultIcon": "#F4F5FA",
    "actionBarActionModeDefaultTop": "#202438",
    "actionBarTabActiveText": "#7C8CFF",
    "actionBarTabUnactiveText": "#A8ADBD",
    "actionBarTabLine": "#7C8CFF",
    "avatar_text": "#FFFFFF",
    "chats_name": "#F4F5FA",
    "chats_nameMessage": "#A8ADBD",
    "chats_message": "#A8ADBD",
    "chats_date": "#7D8496",
    "chats_unreadCounter": "#7C8CFF",
    "chats_unreadCounterText": "#FFFFFF",
    "chats_pinnedIcon": "#7C8CFF",
    "chats_sentCheck": "#7C8CFF",
    "chats_sentReadCheck": "#52E5B5",
    "chats_archiveIcon": "#A8ADBD",
    "chats_onlineCircle": "#52E5B5",
    "chats_draft": "#FF647C",
    "chats_secretIcon": "#52E5B5",
    "chats_actionMessage": "#A8ADBD",
    "chat_wallpaper": "#11131A",
    "chat_messagePanelBackground": "#171B27",
    "chat_messagePanelText": "#F4F5FA",
    "chat_messagePanelHint": "#8991A5",
    "chat_messagePanelIcons": "#A8ADBD",
    "chat_messagePanelSend": "#7C8CFF",
    "chat_messagePanelVoicePressed": "#7C8CFF",
    "chat_inBubble": "#22283A",
    "chat_inBubbleSelected": "#353D58",
    "chat_outBubble": "#34466F",
    "chat_outBubbleSelected": "#435987",
    "chat_messageTextIn": "#F4F5FA",
    "chat_messageTextOut": "#FFFFFF",
    "chat_messageLinkIn": "#9CAEFF",
    "chat_messageLinkOut": "#C7D2FE",
    "chat_inTimeText": "#A8B2CC",
    "chat_outTimeText": "#D6DDF2",
    "chat_inTimeSelectedText": "#DDE3F7",
    "chat_outTimeSelectedText": "#FFFFFF",
    "chat_inSentClock": "#A8B2CC",
    "chat_outSentCheck": "#D6DDF2",
    "chat_outSentCheckRead": "#52E5B5",
    "chat_inReplyLine": "#7C8CFF",
    "chat_outReplyLine": "#A5B4FC",
    "chat_inReplyNameText": "#A5B4FC",
    "chat_outReplyNameText": "#D6DDF2",
    "chat_inReplyMessageText": "#C1C7D8",
    "chat_outReplyMessageText": "#E3E8F8",
    "chat_inForwardedNameText": "#A5B4FC",
    "chat_outForwardedNameText": "#D6DDF2",
    "chat_inViaBotNameText": "#A5B4FC",
    "chat_outViaBotNameText": "#D6DDF2",
    "chat_inReplyMediaMessageSelectedText": "#DDE3F7",
    "chat_outReplyMediaMessageSelectedText": "#FFFFFF",
    "chat_stickerReplyLine": "#7C8CFF",
    "chat_inPreviewLine": "#7C8CFF",
    "chat_outPreviewLine": "#A5B4FC",
    "chat_inFileNameText": "#F4F5FA",
    "chat_outFileNameText": "#FFFFFF",
    "chat_inFileInfoText": "#A8ADBD",
    "chat_outFileInfoText": "#E3E8F8",
    "chat_inFileProgress": "#7C8CFF",
    "chat_outFileProgress": "#C7D2FE",
    "chat_inAudioTitleText": "#F4F5FA",
    "chat_outAudioTitleText": "#FFFFFF",
    "chat_inAudioPerformerText": "#A8ADBD",
    "chat_outAudioPerformerText": "#E3E8F8",
    "chat_inAudioProgress": "#7C8CFF",
    "chat_outAudioProgress": "#C7D2FE",
    "chat_inPollTrack": "#3B4258",
    "chat_outPollTrack": "#59688D",
    "chat_inPollFill": "#7C8CFF",
    "chat_outPollFill": "#D6DDF2",
    "chat_inPollCheck": "#FFFFFF",
    "chat_outPollCheck": "#34466F",
    "chat_inReactionButtonBackground": "#30374D",
    "chat_outReactionButtonBackground": "#52658E",
    "chat_inReactionButtonText": "#F4F5FA",
    "chat_outReactionButtonText": "#FFFFFF",
    "chat_emojiPanelBackground": "#151824",
    "chat_emojiPanelIcon": "#A8ADBD",
    "chat_emojiPanelIconSelected": "#7C8CFF",
    "chat_emojiPanelStickerPackSelector": "#7C8CFF",
    "chat_attachPanelBackground": "#151824",
    "chat_attachPanelText": "#F4F5FA",
    "chat_attachPanelIcon": "#A8ADBD",
    "chat_previewGameText": "#F4F5FA",
    "chat_previewGameTextShadow": "#11131A",
    "chat_botButtonText": "#FFFFFF",
    "chat_botButtonBackground": "#7C8CFF",
    "chat_botKeyboardButtonBackground": "#22283A",
    "chat_botKeyboardButtonText": "#F4F5FA",
    "chat_goDownButton": "#202438",
    "chat_goDownButtonIcon": "#F4F5FA",
    "chat_unreadMessagesStartBackground": "#202438",
    "chat_unreadMessagesStartText": "#F4F5FA",
    "chat_inQuote": "#A5B4FC",
    "chat_outQuote": "#D6DDF2",
    "chat_inCodeBackground": "#171B27",
    "chat_outCodeBackground": "#283653",
    "chat_inCodeText": "#C7D2FE",
    "chat_outCodeText": "#FFFFFF",
    "divider": "#292E40",
    "checkbox": "#7C8CFF",
    "checkboxCheck": "#FFFFFF",
    "radioBackground": "#7C8CFF",
    "switchTrack": "#41485C",
    "switchTrackChecked": "#7C8CFF",
    "switchTrackBlue": "#7C8CFF",
    "switchTrackBlueChecked": "#7C8CFF",
    "windowBackgroundWhiteInputField": "#202438",
    "windowBackgroundWhiteInputFieldActivated": "#7C8CFF",
    "windowBackgroundWhiteHintText": "#8991A5",
    "featuredStickers_addButton": "#7C8CFF",
    "featuredStickers_buttonText": "#FFFFFF",
    "profile_actionIcon": "#7C8CFF",
    "profile_actionBackground": "#202438",
    "profile_verifiedBackground": "#7C8CFF",
    "profile_verifiedCheck": "#FFFFFF",
    "contextProgressInner1": "#7C8CFF",
    "contextProgressOuter1": "#30374D",
    "location_marker": "#7C8CFF",
}

def clamp(value, low=0, high=255):
    return max(low, min(high, int(value)))

def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

def rgb_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*[clamp(x) for x in rgb])

def mix(a, b, amount):
    aa, bb = hex_rgb(a), hex_rgb(b)
    return rgb_hex(tuple(aa[i] * (1 - amount) + bb[i] * amount for i in range(3)))

def readable_text(bg):
    r, g, b = hex_rgb(bg)
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b)
    return "#101116" if luminance > 155 else "#F7F8FF"

def image_palette(image):
    sample = image.copy()
    sample.thumbnail((180, 180))
    sample = sample.convert("RGB").quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    palette = sample.getpalette() or []
    counts = Counter(sample.getdata())
    colors = []
    for idx, _count in counts.most_common():
        base = idx * 3
        if base + 2 < len(palette):
            rgb = tuple(palette[base:base+3])
            # Ignore near-black / near-white as primary accent when possible.
            colors.append(rgb)
    colorful = [c for c in colors if max(c) - min(c) > 24 and max(c) > 65]
    return colorful or colors or [(124, 140, 255)]

def stylize_color(rgb, saturation_factor, brightness_factor):
    r, g, b = [v / 255.0 for v in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = max(0.38, min(1.0, s * saturation_factor))
    v = max(0.35, min(1.0, v * brightness_factor))
    return rgb_hex(tuple(round(x * 255) for x in colorsys.hsv_to_rgb(h, s, v)))

def create_theme(image_bytes, style_key):
    with Image.open(io.BytesIO(image_bytes)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
        # Save the actual submitted wallpaper in a Telegram .attheme WPS/WPE section.
        wallpaper = io.BytesIO()
        image.save(wallpaper, format="JPEG", quality=92, optimize=True, progressive=False)
        wallpaper_bytes = wallpaper.getvalue()
        palette = image_palette(image)

    style = STYLES.get(style_key, STYLES["wall"])
    main = stylize_color(palette[0], style["sat"], style["bright"])
    secondary = stylize_color(palette[1] if len(palette) > 1 else palette[0], style["sat"], style["bright"])
    accent = style["accent"] or main
    second = style["second"] or secondary

    # Make the UI dark, but do NOT use a black chat wallpaper: WPS embeds the user's image below.
    bg = mix(main, "#10131D", 0.86)
    panel = mix(main, "#171B29", 0.79)
    incoming = mix(secondary, "#252B3D", 0.70)
    outgoing = mix(accent, "#252B3D", 0.48)
    text = readable_text(bg)
    muted = mix(text, bg, 0.36)
    colors = dict(BASE_COLORS)
    replacements = {
        "windowBackgroundWhite": panel,
        "windowBackgroundWhiteBlackText": text,
        "windowBackgroundWhiteGrayText": muted,
        "windowBackgroundWhiteGrayText2": mix(muted, bg, 0.25),
        "windowBackgroundWhiteGrayText3": mix(muted, bg, 0.38),
        "windowBackgroundWhiteGrayText4": mix(muted, bg, 0.48),
        "windowBackgroundWhiteBlueText": accent,
        "windowBackgroundWhiteLinkText": accent,
        "windowBackgroundWhiteLinkSelection": second,
        "windowBackgroundGray": bg,
        "actionBarDefault": panel,
        "actionBarDefaultIcon": text,
        "actionBarDefaultTitle": text,
        "actionBarDefaultSubtitle": muted,
        "actionBarDefaultSelector": mix(accent, panel, 0.76),
        "actionBarDefaultSearch": text,
        "actionBarDefaultSearchPlaceholder": muted,
        "actionBarActionModeDefault": mix(accent, panel, 0.78),
        "actionBarActionModeDefaultIcon": text,
        "actionBarActionModeDefaultTop": mix(accent, panel, 0.78),
        "actionBarTabActiveText": accent,
        "actionBarTabUnactiveText": muted,
        "actionBarTabLine": accent,
        "chats_name": text,
        "chats_nameMessage": muted,
        "chats_message": muted,
        "chats_date": muted,
        "chats_unreadCounter": accent,
        "chats_pinnedIcon": accent,
        "chats_sentCheck": accent,
        "chats_sentReadCheck": second,
        "chats_onlineCircle": second,
        "chats_draft": second,
        "chat_wallpaper": bg,
        "chat_messagePanelBackground": panel,
        "chat_messagePanelText": text,
        "chat_messagePanelHint": muted,
        "chat_messagePanelIcons": muted,
        "chat_messagePanelSend": accent,
        "chat_messagePanelVoicePressed": accent,
        "chat_inBubble": incoming,
        "chat_inBubbleSelected": mix(incoming, accent, 0.35),
        "chat_outBubble": outgoing,
        "chat_outBubbleSelected": mix(outgoing, second, 0.30),
        "chat_messageTextIn": readable_text(incoming),
        "chat_messageTextOut": readable_text(outgoing),
        "chat_messageLinkIn": accent,
        "chat_messageLinkOut": second,
        "chat_inTimeText": mix(readable_text(incoming), incoming, 0.25),
        "chat_outTimeText": mix(readable_text(outgoing), outgoing, 0.25),
        "chat_inReplyLine": accent,
        "chat_outReplyLine": second,
        "chat_inReplyNameText": accent,
        "chat_outReplyNameText": second,
        "chat_inForwardedNameText": accent,
        "chat_outForwardedNameText": second,
        "chat_inViaBotNameText": accent,
        "chat_outViaBotNameText": second,
        "chat_inFileProgress": accent,
        "chat_outFileProgress": second,
        "chat_inAudioProgress": accent,
        "chat_outAudioProgress": second,
        "chat_inPollFill": accent,
        "chat_outPollFill": second,
        "chat_inReactionButtonBackground": mix(incoming, accent, 0.24),
        "chat_outReactionButtonBackground": mix(outgoing, second, 0.24),
        "chat_emojiPanelBackground": panel,
        "chat_emojiPanelIconSelected": accent,
        "chat_emojiPanelStickerPackSelector": accent,
        "chat_attachPanelBackground": panel,
        "chat_attachPanelText": text,
        "chat_attachPanelIcon": accent,
        "chat_botButtonText": readable_text(accent),
        "chat_botButtonBackground": accent,
        "chat_botKeyboardButtonBackground": panel,
        "chat_botKeyboardButtonText": text,
        "chat_goDownButton": panel,
        "chat_goDownButtonIcon": accent,
        "chat_unreadMessagesStartBackground": panel,
        "chat_unreadMessagesStartText": text,
        "chat_inQuote": accent,
        "chat_outQuote": second,
        "chat_inCodeBackground": panel,
        "chat_outCodeBackground": mix(outgoing, panel, 0.42),
        "chat_inCodeText": accent,
        "chat_outCodeText": text,
        "divider": mix(panel, text, 0.12),
        "checkbox": accent,
        "radioBackground": accent,
        "switchTrackChecked": accent,
        "switchTrackBlue": accent,
        "switchTrackBlueChecked": accent,
        "windowBackgroundWhiteInputField": bg,
        "windowBackgroundWhiteInputFieldActivated": accent,
        "windowBackgroundWhiteHintText": muted,
        "featuredStickers_addButton": accent,
        "featuredStickers_buttonText": readable_text(accent),
        "profile_actionIcon": accent,
        "profile_actionBackground": panel,
        "profile_verifiedBackground": accent,
        "contextProgressInner1": accent,
        "contextProgressOuter1": mix(accent, panel, 0.72),
        "location_marker": accent,
    }
    colors.update(replacements)

    # Telegram theme values, then embedded JPEG wallpaper. WPS/WPE are Telegram's wallpaper markers.
    lines = ["// Spike Theme Studio - generated from your wallpaper"]
    for key, value in colors.items():
        lines.append(f"{key}={value}")
    header = ("\n".join(lines) + "\nWPS\n").encode("utf-8")
    return header + wallpaper_bytes + b"\nWPE\n"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("⚡ نئونی", callback_data="style:neon"),
            InlineKeyboardButton("🎴 انیمه‌ای", callback_data="style:anime"),
        ],
        [
            InlineKeyboardButton("🌆 سایبرپانک", callback_data="style:cyber"),
            InlineKeyboardButton("🧊 آبی یخی", callback_data="style:ice"),
        ],
        [
            InlineKeyboardButton("💜 بنفش الکتریکی", callback_data="style:purple"),
            InlineKeyboardButton("🔴 قرمز تیره", callback_data="style:red"),
        ],
        [
            InlineKeyboardButton("🖤 دارک لوکس", callback_data="style:lux"),
            InlineKeyboardButton("🎨 هماهنگ با عکس", callback_data="style:wall"),
        ],
    ]
    context.user_data.pop("theme_style", None)
    await update.effective_message.reply_text(
        "🎨 سبک تم رو انتخاب کن؛ بعد والپیپرت رو بفرست تا رنگ‌های کل رابط تلگرام باهاش هماهنگ بشن.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def choose_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    style_key = query.data.split(":", 1)[1]
    if style_key not in STYLES:
        await query.edit_message_text("این سبک معتبر نیست. دوباره /start بزن.")
        return
    context.user_data["theme_style"] = style_key
    await query.edit_message_text(
        f"سبک «{STYLES[style_key]['name']}» انتخاب شد.\nحالا خودِ والپیپر رو به صورت عکس بفرست (نه اسکرین‌شات پیش‌نمایش تم)."
    )

async def receive_wallpaper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    style_key = context.user_data.get("theme_style")
    if not style_key:
        await update.effective_message.reply_text("اول /start بزن و سبک تم رو انتخاب کن.")
        return
    message = update.effective_message
    photo_bytes = None
    try:
        if message.photo:
            file = await message.photo[-1].get_file()
            data = await file.download_as_bytearray()
            photo_bytes = bytes(data)
        elif message.document and (message.document.mime_type or "").startswith("image/"):
            file = await message.document.get_file()
            data = await file.download_as_bytearray()
            photo_bytes = bytes(data)
        else:
            await message.reply_text("لطفاً خودِ والپیپر رو به صورت عکس یا فایل تصویری بفرست.")
            return

        await message.reply_text("⚙️ دارم رنگ‌ها رو از عکس درمیارم و فایل تم رو می‌سازم...")
        theme_data = create_theme(photo_bytes, style_key)
        filename = f"Spike_{style_key}.attheme"
        await message.reply_document(
            document=io.BytesIO(theme_data),
            filename=filename,
            caption=(
                f"تم «{STYLES[style_key]['name']}» ساخته شد.\n"
                "والپیپر اصلی داخل فایل قرار داده شده؛ روی تلگرام اندروید بازش کن و Apply بزن."
            ),
        )
        context.user_data.pop("theme_style", None)
    except Exception:
        log.exception("Failed to create theme")
        await message.reply_text("ساخت تم با خطا روبه‌رو شد. دوباره /start بزن و عکس رو مجدداً بفرست.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("theme_style", None)
    await update.effective_message.reply_text("لغو شد. برای شروع دوباره /start بزن.")

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(choose_style, pattern=r"^style:"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_wallpaper))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, receive_wallpaper))
    log.info("Spike Theme Studio starting")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
