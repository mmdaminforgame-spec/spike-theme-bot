import io
import os
import re
import logging
import colorsys
from collections import Counter

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance, ImageFilter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("spike-theme-v2")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
WAIT_NAME, WAIT_PHOTO = range(2)
STYLES = {
    "balanced": ("متعادل", 0.55),
    "vivid": ("پررنگ", 0.88),
    "soft": ("ملایم", 0.30),
    "minimal": ("مینیمال", 0.40),
}

def safe_name(value):
    value = re.sub(r"[^a-zA-Z0-9آ-ی _-]", "", (value or "").strip())
    value = re.sub(r"\s+", "_", value)[:48].strip("_")
    return value or "SpikeTheme"

def blend(a, b, amount):
    amount = max(0.0, min(1.0, float(amount)))
    return tuple(round(x * (1 - amount) + y * amount) for x, y in zip(a, b))

def luminance(rgb):
    def channel(v):
        v = v / 255.0
        return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb)
    return .2126*r + .7152*g + .0722*b

def contrast_text(bg):
    return (248, 249, 252) if luminance(bg) < .42 else (25, 28, 34)

def normalized_image(image_bytes, max_side=2560):
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        im.save(out, "JPEG", quality=94, optimize=True, progressive=False, subsampling=0)
        data = out.getvalue()
    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        raise ValueError("JPEG conversion failed")
    return data

def analyze_palette(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as src:
        im = ImageOps.exif_transpose(src).convert("RGB")
        im.thumbnail((420, 420), Image.Resampling.LANCZOS)
        quant = im.quantize(colors=24, method=Image.Quantize.MEDIANCUT)
        palette = quant.getpalette() or []
        counts = quant.getcolors(maxcolors=420*420) or []
        ranked = []
        for count, idx in counts:
            rgb = tuple(palette[idx*3:idx*3+3])
            if len(rgb) == 3:
                chroma = max(rgb)-min(rgb)
                ranked.append((count * (0.8 + min(1, chroma/110)*.2), rgb))
    ranked.sort(reverse=True)
    result = []
    for _, rgb in ranked:
        if all(sum(abs(a-b) for a,b in zip(rgb, old)) > 38 for old in result):
            result.append(rgb)
        if len(result) >= 12:
            break
    if not result:
        return [(68, 115, 220), (25, 29, 42)]
    return result

def build_colors(palette, mode="dark", style="balanced"):
    # Accent selection favors vivid colors while avoiding nearly white/black accents.
    candidates = [c for c in palette if .12 < luminance(c) < .78]
    accent = max(candidates or palette, key=lambda c: (max(c)-min(c)) * .72 + sum(c)/765*.12)
    h, s, v = colorsys.rgb_to_hsv(*(x/255 for x in accent))
    boost = STYLES.get(style, STYLES["balanced"])[1]
    accent = tuple(round(x*255) for x in colorsys.hsv_to_rgb(
        h, min(1, max(.24, s*(.55+boost))), min(.95, max(.42, v))))
    base = palette[0]
    if mode == "light":
        bg = blend((249, 250, 253), base, .09 if style == "minimal" else .15)
        panel = blend((255,255,255), base, .06)
        text, hint = (28,31,39), (102,110,124)
        incoming = blend((239,242,247), base, .10)
        outgoing = blend((224,242,229), accent, .30 if style == "vivid" else .19)
        divider = (222,226,233)
    else:
        bg = blend((17,20,28), base, .11 if style == "minimal" else .20)
        panel = blend((27,31,41), base, .13 if style == "soft" else .20)
        text, hint = (241,244,250), (158,167,182)
        incoming = blend((38,43,55), base, .17 if style == "soft" else .25)
        outgoing = blend((35,65,69), accent, .38 if style == "vivid" else .27)
        divider = blend((58,64,77), base, .12)
    out_text = contrast_text(outgoing)
    # Broad set of common Android Telegram theme keys. Unsupported keys are ignored by Telegram.
    return {
        "windowBackgroundWhite": bg, "windowBackgroundGray": panel,
        "actionBarDefault": panel, "actionBarDefaultIcon": text,
        "actionBarDefaultTitle": text, "actionBarDefaultSubtitle": hint,
        "actionBarDefaultSelector": blend(accent, panel, .72),
        "windowBackgroundWhiteBlackText": text, "windowBackgroundWhiteGrayText": hint,
        "windowBackgroundWhiteBlueText": accent, "windowBackgroundWhiteLinkText": accent,
        "windowBackgroundWhiteLinkSelection": blend(accent, bg, .25),
        "windowBackgroundWhiteHintText": hint, "windowBackgroundWhiteInputField": divider,
        "chat_inBubble": incoming, "chat_outBubble": outgoing,
        "chat_messageTextIn": text, "chat_messageTextOut": out_text,
        "chat_inTimeText": hint, "chat_outTimeText": out_text,
        "chat_status": accent, "chat_outSentCheck": accent,
        "chat_outSentCheckSelected": accent, "chats_menuTopBackground": panel,
        "chats_menuTopShadow": divider, "divider": divider,
        "listSelectorSDK21": blend(accent, bg, .70), "checkbox": accent,
        "radioBackground": accent, "switchTrack": hint, "switchTrackChecked": accent,
        "switchThumb": (246,246,246), "switchThumbChecked": (255,255,255),
        "avatar_backgroundBlue": accent, "avatar_text": (255,255,255),
        "actionBarDefaultSearch": text, "actionBarDefaultSearchPlaceholder": hint,
        "chat_emojiPanelBackground": panel, "chat_emojiPanelIcon": hint,
        "chat_emojiPanelIconSelected": accent, "chat_messagePanelBackground": panel,
        "chat_messagePanelText": text, "chat_messagePanelHint": hint,
        "chat_messagePanelSend": accent, "chat_attachMessageBackground": accent,
        "chat_wallpaper": bg, "chat_serviceBackground": blend(panel, accent, .22),
        "chat_serviceText": text, "chat_inReplyLine": accent, "chat_outReplyLine": accent,
        "chat_inReplyNameText": accent, "chat_outReplyNameText": out_text,
        "chat_inForwardedNameText": accent, "chat_outForwardedNameText": out_text,
        "chat_inReplyMessageText": hint, "chat_outReplyMessageText": out_text,
        "chat_recordedVoiceBackground": accent, "chat_recordedVoiceDot": accent,
        "chat_inLoader": accent, "chat_outLoader": out_text,
        "chat_inFileProgress": accent, "chat_outFileProgress": out_text,
        "chat_inFileNameText": text, "chat_outFileNameText": out_text,
        "chat_inFileInfoText": hint, "chat_outFileInfoText": out_text,
        "chat_inAudioTitleText": text, "chat_outAudioTitleText": out_text,
        "chat_inAudioPerformerText": hint, "chat_outAudioPerformerText": out_text,
    }

def make_attheme(colors, wallpaper_bytes):
    """Return a binary Android .attheme with a JPEG embedded between WPS/WPE."""
    lines = []
    for key, rgb in colors.items():
        r, g, b = (max(0, min(255, int(x))) for x in rgb)
        lines.append(f"{key}=#FF{r:02X}{g:02X}{b:02X}")
    jpeg = normalized_image(wallpaper_bytes)
    header = ("\n".join(lines) + "\nWPS\n").encode("utf-8")
    result = header + jpeg + b"\nWPE\n"
    if b"\nWPS\n" not in result or not result.endswith(b"\nWPE\n"):
        raise ValueError("Invalid .attheme wallpaper framing")
    return result

def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()

def make_preview(image_bytes, colors, name, mode, style):
    W, H = 1000, 700
    bg, panel = colors["windowBackgroundWhite"], colors["actionBarDefault"]
    text, hint = colors["actionBarDefaultTitle"], colors["actionBarDefaultSubtitle"]
    accent, inc, out = colors["windowBackgroundWhiteBlueText"], colors["chat_inBubble"], colors["chat_outBubble"]
    im = Image.new("RGB", (W,H), bg)
    d = ImageDraw.Draw(im)
    d.text((32,24), "SPIKE THEME STUDIO", font=get_font(17, True), fill=accent)
    d.text((32,54), name[:42], font=get_font(28, True), fill=text)
    d.text((32,96), f"{mode.upper()}  •  {STYLES.get(style, STYLES['balanced'])[0]}  •  WALLPAPER EMBEDDED", font=get_font(14), fill=hint)
    d.rounded_rectangle((25,140,975,675), radius=24, fill=panel)
    d.rounded_rectangle((42,158,330,655), radius=18, fill=bg)
    d.text((62,175), "Chats", font=get_font(22, True), fill=text)
    d.text((62,210), "Search messages", font=get_font(13), fill=hint)
    y=260
    for idx,(title,sub) in enumerate([("Mina","Sent you a photo"),("Design group","That palette is clean"),("Saved Messages","Theme concept"),("Spike","Looks good ✓")]):
        if idx==0: d.rounded_rectangle((51,y-8,318,y+58),radius=13,fill=inc)
        d.ellipse((62,y,100,y+38),fill=blend(accent,bg,.24))
        d.text((111,y+1),title,font=get_font(14,True),fill=text)
        d.text((111,y+25),sub,font=get_font(10),fill=hint)
        y+=83
    d.rounded_rectangle((350,158,957,655),radius=18,fill=bg)
    d.rounded_rectangle((350,158,957,215),radius=18,fill=panel)
    d.text((372,174),"Spike Theme Preview",font=get_font(17,True),fill=text)
    try:
        with Image.open(io.BytesIO(image_bytes)) as src:
            wall=ImageOps.fit(src.convert("RGB"),(580,365))
            wall=ImageEnhance.Brightness(wall).enhance(.27 if mode=="dark" else .42)
            wall=ImageEnhance.Color(wall).enhance(.65)
            wall=wall.filter(ImageFilter.GaussianBlur(1))
            im.paste(wall,(363,230))
    except Exception:
        pass
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((386,266,625,322),radius=15,fill=inc)
    d.text((402,279),"The colors fit this wallpaper.",font=get_font(12),fill=colors["chat_messageTextIn"])
    d.text((402,302),"09:41",font=get_font(9),fill=hint)
    d.rounded_rectangle((625,344,927,408),radius=15,fill=out)
    d.text((642,359),"A custom theme, made for you.",font=get_font(12),fill=colors["chat_messageTextOut"])
    d.text((642,385),"09:42  ✓✓",font=get_font(9),fill=colors["chat_messageTextOut"])
    d.rounded_rectangle((380,586,927,635),radius=19,fill=panel)
    d.text((400,601),"Message",font=get_font(12),fill=hint)
    return im

def main_menu(uid):
    rows = [
        [InlineKeyboardButton("🎨 ساخت تم جدید", callback_data="new")],
        [InlineKeyboardButton("🌙 تیره", callback_data="mode:dark"), InlineKeyboardButton("☀️ روشن", callback_data="mode:light")],
        [InlineKeyboardButton("🎛 سبک رنگ‌بندی", callback_data="styles"), InlineKeyboardButton("📖 راهنما", callback_data="help")],
    ]
    if OWNER_ID and uid == OWNER_ID:
        rows.append([InlineKeyboardButton("👑 پنل مالک", callback_data="admin")])
    return InlineKeyboardMarkup(rows)

def style_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("متعادل", callback_data="style:balanced"), InlineKeyboardButton("پررنگ", callback_data="style:vivid")],
        [InlineKeyboardButton("ملایم", callback_data="style:soft"), InlineKeyboardButton("مینیمال", callback_data="style:minimal")],
        [InlineKeyboardButton("↩️ منوی اصلی", callback_data="home")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("mode", "dark")
    context.user_data.setdefault("style", "balanced")
    await update.effective_message.reply_text(
        "✦ SPIKE THEME STUDIO V2\n\n"
        "والپیپر رو بفرست؛ رنگ‌بندی اختصاصی ساخته می‌شه و خود تصویر داخل فایل .attheme قرار می‌گیره.\n"
        "برای شروع «ساخت تم جدید» رو بزن.",
        reply_markup=main_menu(update.effective_user.id))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("لغو شد.", reply_markup=main_menu(update.effective_user.id))
    return ConversationHandler.END

async def begin_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    await q.message.reply_text("اسم تم رو بفرست؛ مثلاً Neon Rain یا Spike Ocean.\nلغو: /cancel")
    return WAIT_NAME

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("اسم تم رو بفرست:\nلغو: /cancel")
    return WAIT_NAME

async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["project_name"] = safe_name(update.effective_message.text)
    await update.effective_message.reply_text(
        f"اسم ثبت شد: {context.user_data['project_name']}\n"
        "حالا والپیپر رو به شکل عکس (Photo) بفرست.")
    return WAIT_PHOTO

async def got_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg=update.effective_message
    try:
        if not msg or not msg.photo:
            await msg.reply_text("والپیپر رو با گزینهٔ Photo بفرست.")
            return WAIT_PHOTO
        await msg.reply_text("🔬 دارم تصویر رو تحلیل می‌کنم، رنگ‌ها رو می‌سازم و والپیپر رو داخل فایل جاسازی می‌کنم…")
        tgfile=await msg.photo[-1].get_file()
        buf=io.BytesIO()
        await tgfile.download_to_memory(out=buf)
        image_bytes=buf.getvalue()
        if not image_bytes or len(image_bytes)>15*1024*1024:
            await msg.reply_text("حجم عکس باید کمتر از ۱۵ مگابایت باشه؛ نسخهٔ سبک‌تر رو بفرست.")
            return WAIT_PHOTO
        with Image.open(io.BytesIO(image_bytes)) as im:
            im.verify()
        palette=analyze_palette(image_bytes)
        mode=context.user_data.get("mode","dark")
        style=context.user_data.get("style","balanced")
        project=safe_name(context.user_data.get("project_name","SpikeTheme"))
        colors=build_colors(palette,mode,style)
        theme_bytes=make_attheme(colors,image_bytes)
        preview=make_preview(image_bytes,colors,project,mode,style)
        pbuf=io.BytesIO()
        preview.save(pbuf,format="PNG",optimize=True)
        pbuf.seek(0)
        await msg.reply_document(
            document=InputFile(io.BytesIO(theme_bytes),filename=f"{project}_{mode}.attheme"),
            caption=f"🎨 تم اختصاصی آماده شد: {project}\n"
                    f"حالت: {'تیره' if mode=='dark' else 'روشن'} | سبک: {STYLES.get(style,STYLES['balanced'])[0]}\n\n"
                    "والپیپر داخل همین فایل .attheme جاسازی شده؛ فایل رو در تلگرام اندروید باز کن و اعمال کن.")
        await msg.reply_photo(
            photo=InputFile(pbuf,filename=f"{project}_preview.png"),
            caption="🖼 پیش‌نمایش طراحی‌شده از رنگ‌بندی تم (ماکت تصویری، نه اسکرین‌شات واقعی تلگرام).")
        await msg.reply_document(
            document=InputFile(io.BytesIO(image_bytes),filename=f"{project}_original_wallpaper"),
            caption="نسخهٔ اصلی عکس برای نگه‌داشتن جداگانه؛ نسخهٔ داخل تم هم جاسازی شده.")
        await msg.reply_text("تمام شد. برای تم بعدی از منو استفاده کن.",reply_markup=main_menu(update.effective_user.id))
        return ConversationHandler.END
    except Exception:
        log.exception("Theme creation failed")
        await msg.reply_text("ساخت تم انجام نشد. عکس JPG یا PNG دیگه‌ای امتحان کن؛ جزئیات خطا در گزارش هاست ثبت شد.")
        return WAIT_PHOTO

async def photo_outside_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("اول «🎨 ساخت تم جدید» رو بزن.",reply_markup=main_menu(update.effective_user.id))

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    data=q.data or ""
    uid=update.effective_user.id
    if data=="home":
        await q.message.reply_text("منوی اصلی:",reply_markup=main_menu(uid))
    elif data=="styles":
        await q.message.reply_text("سبک رنگ‌بندی رو انتخاب کن:",reply_markup=style_menu())
    elif data.startswith("style:"):
        style=data.split(":",1)[1]
        if style in STYLES: context.user_data["style"]=style
        await q.message.reply_text("سبک انتخاب شد: "+STYLES.get(style,STYLES["balanced"])[0],reply_markup=main_menu(uid))
    elif data.startswith("mode:"):
        mode=data.split(":",1)[1]
        if mode in ("dark","light"): context.user_data["mode"]=mode
        await q.message.reply_text("حالت انتخاب شد: "+("تیره" if mode=="dark" else "روشن"),reply_markup=main_menu(uid))
    elif data=="help":
        await q.message.reply_text(
            "۱) ساخت تم جدید\n۲) وارد کردن اسم\n۳) فرستادن والپیپر به شکل Photo\n"
            "۴) دریافت .attheme با تصویر جاسازی‌شده، پیش‌نمایش و عکس اصلی.\n\n"
            "اعمال تم: فایل .attheme رو در تلگرام اندروید باز کن و Apply رو بزن.",
            reply_markup=main_menu(uid))
    elif data=="admin":
        if not OWNER_ID or uid!=OWNER_ID:
            await q.message.reply_text("این بخش فقط برای مالک رباته.")
        else:
            await q.message.reply_text("ربات فعال است. برای گزارش خطاها Console هاست را بررسی کن.")

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled Telegram error",exc_info=context.error)

def main():
    if not TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")
    app=Application.builder().token(TOKEN).build()
    flow=ConversationHandler(
        entry_points=[CallbackQueryHandler(begin_new,pattern="^new$"),CommandHandler("new",new_command)],
        states={
            WAIT_NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND,got_name)],
            WAIT_PHOTO:[MessageHandler(filters.PHOTO,got_photo)],
        },
        fallbacks=[CommandHandler("cancel",cancel)],
        allow_reentry=True,
    )
    app.add_handler(CommandHandler("start",start))
    app.add_handler(flow)
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO,photo_outside_flow))
    app.add_error_handler(on_error)
    log.info("Spike Theme Studio v2 starting")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
