import os
import io
import re
import logging
import colorsys
import sqlite3
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("spike-theme")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
DB_PATH = os.getenv("SPIKE_DB_PATH", "spike_theme.db")
WAIT_NAME, WAIT_PHOTO = range(2)

STYLES = {
    "balanced": ("متعادل", 0.50),
    "vivid": ("پررنگ", 0.78),
    "soft": ("ملایم", 0.30),
    "minimal": ("مینیمال", 0.42),
}

def db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_seen TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS themes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, project_name TEXT,
        mode TEXT, style TEXT, created_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, detail TEXT, created_at TEXT)""")
    con.commit()
    return con

def record_user(user):
    if not user:
        return
    con = db()
    con.execute("INSERT OR IGNORE INTO users(user_id, username, first_seen) VALUES(?,?,?)",
                (user.id, user.username or "", datetime.now(timezone.utc).isoformat()))
    con.execute("UPDATE users SET username=? WHERE user_id=?", (user.username or "", user.id))
    con.commit()
    con.close()

def record_theme(user_id, name, mode, style):
    con = db()
    con.execute("INSERT INTO themes(user_id, project_name, mode, style, created_at) VALUES(?,?,?,?,?)",
                (user_id, name, mode, style, datetime.now(timezone.utc).isoformat()))
    con.commit()
    con.close()

def record_error(user_id, detail):
    con = db()
    con.execute("INSERT INTO errors(user_id, detail, created_at) VALUES(?,?,?)",
                (user_id, detail[:500], datetime.now(timezone.utc).isoformat()))
    con.commit()
    con.close()

def safe_name(name):
    name = re.sub(r"[^a-zA-Z0-9آ-ی _-]", "", (name or "").strip())
    name = re.sub(r"\s+", "_", name)[:48].strip("_")
    return name or "SpikeTheme"

def rgb_hex(rgb):
    return "{:02X}{:02X}{:02X}".format(*[max(0, min(255, int(x))) for x in rgb])

def blend(a, b, amount):
    amount = max(0.0, min(1.0, amount))
    return tuple(round(x * (1 - amount) + y * amount) for x, y in zip(a, b))

def luminance(rgb):
    vals = [v / 255 for v in rgb]
    def channel(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [channel(c) for c in vals]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def readable_text(bg):
    return (245, 247, 252) if luminance(bg) < 0.40 else (28, 31, 38)

def analyze_palette(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as source:
        im = source.convert("RGB")
        im.thumbnail((256, 256))
        quant = im.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
        palette = quant.getpalette() or []
        counts = quant.getcolors() or []
        counts.sort(reverse=True)
        ranked = []
        for count, index in counts:
            rgb = tuple(palette[index * 3:index * 3 + 3])
            if len(rgb) == 3 and count:
                chroma = max(rgb) - min(rgb)
                score = count * (0.75 + min(1.0, chroma / 110) * 0.25)
                ranked.append((score, rgb))
        ranked.sort(reverse=True)
        unique = []
        for _, rgb in ranked:
            if all(sum(abs(a-b) for a,b in zip(rgb, old)) > 42 for old in unique):
                unique.append(rgb)
            if len(unique) >= 8:
                break
        return unique or [(70, 120, 220), (35, 40, 55)]

def build_colors(palette, mode, style):
    base = palette[0]
    accent = max(palette, key=lambda c: (max(c)-min(c)) * 0.7 + sum(c)/765 * 0.3)
    if luminance(accent) > 0.72:
        accent = blend(accent, (30, 50, 90), 0.38)
    if luminance(accent) < 0.07:
        accent = blend(accent, (90, 120, 180), 0.62)
    saturation = STYLES.get(style, STYLES["balanced"])[1]
    h, s, v = colorsys.rgb_to_hsv(*(x/255 for x in accent))
    accent = tuple(round(x*255) for x in colorsys.hsv_to_rgb(
        h, min(1, max(0.18, s * (0.6 + saturation))),
        min(1, max(0.35, v))))
    if mode == "light":
        bg = blend((250, 251, 254), base, 0.08 if style == "minimal" else 0.16)
        panel, text, hint = (255, 255, 255), (28, 31, 40), (105, 112, 126)
        incoming = blend((239, 242, 247), base, 0.10)
        outgoing = blend((220, 242, 225), accent, 0.36 if style == "vivid" else 0.22)
        divider = (224, 228, 235)
    else:
        bg = blend((17, 20, 28), base, 0.10 if style == "minimal" else 0.20)
        panel = blend((27, 31, 41), base, 0.10 if style == "soft" else 0.18)
        text, hint = (241, 244, 250), (157, 166, 181)
        incoming = blend((37, 42, 54), base, 0.16 if style == "soft" else 0.25)
        outgoing = blend((34, 67, 70), accent, 0.38 if style == "vivid" else 0.27)
        divider = (57, 63, 76)
    out_text = readable_text(outgoing)
    return {
        "windowBackgroundWhite": bg, "windowBackgroundGray": panel,
        "actionBarDefault": panel, "actionBarDefaultIcon": text,
        "actionBarDefaultTitle": text, "actionBarDefaultSubtitle": hint,
        "windowBackgroundWhiteBlackText": text, "windowBackgroundWhiteGrayText": hint,
        "windowBackgroundWhiteBlueText": accent, "windowBackgroundWhiteLinkText": accent,
        "windowBackgroundWhiteLinkSelection": accent, "chat_inBubble": incoming,
        "chat_outBubble": outgoing, "chat_messageTextIn": text,
        "chat_messageTextOut": out_text, "chat_inTimeText": hint,
        "chat_outTimeText": out_text, "chat_status": accent, "chat_outSentCheck": accent,
        "chat_outSentCheckSelected": accent, "chats_menuTopBackground": panel,
        "chats_menuTopShadow": divider, "divider": divider,
        "listSelectorSDK21": blend(accent, bg, 0.65), "checkbox": accent,
        "radioBackground": accent, "switchTrack": hint, "switchTrackChecked": accent,
        "switchThumb": (245, 245, 245), "switchThumbChecked": (255, 255, 255),
        "avatar_backgroundBlue": accent, "avatar_text": (255, 255, 255),
        "actionBarDefaultSearch": text, "actionBarDefaultSearchPlaceholder": hint,
        "chat_emojiPanelBackground": panel, "chat_emojiPanelIcon": hint,
        "chat_emojiPanelIconSelected": accent, "chat_messagePanelBackground": panel,
        "chat_messagePanelText": text, "chat_messagePanelHint": hint,
        "chat_messagePanelSend": accent, "chat_attachMessageBackground": accent,
        "chat_wallpaper": bg, "chat_serviceBackground": blend(panel, accent, 0.22),
        "chat_serviceText": text, "chat_inReplyLine": accent, "chat_outReplyLine": accent,
        "chat_inReplyNameText": accent, "chat_outReplyNameText": out_text,
    }

def make_attheme(colors):
    return "\n".join(f"{key}={rgb_hex(value)}" for key, value in colors.items()) + "\n"

def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()

def make_preview(image_bytes, colors, project_name, mode, style):
    # Illustrative Telegram-style mockup, not an official Telegram screenshot.
    W, H = 1100, 760
    bg, panel = colors["windowBackgroundWhite"], colors["actionBarDefault"]
    text, hint, accent = colors["actionBarDefaultTitle"], colors["actionBarDefaultSubtitle"], colors["windowBackgroundWhiteBlueText"]
    incoming, outgoing = colors["chat_inBubble"], colors["chat_outBubble"]
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.text((42, 26), "SPIKE THEME STUDIO", font=font(19, True), fill=accent)
    d.text((42, 58), project_name[:42], font=font(30, True), fill=text)
    d.text((42, 101), f"{mode.upper()}  •  {STYLES.get(style, STYLES['balanced'])[0]}  •  COLOR-MATCHED", font=font(15), fill=hint)
    d.rounded_rectangle((34,145,1066,718), radius=28, fill=panel)
    d.rounded_rectangle((54,166,390,697), radius=22, fill=bg)
    d.text((76,184), "Chats", font=font(24, True), fill=text)
    d.text((76,220), "Search messages", font=font(14), fill=hint)
    for i, c in enumerate(list(colors.values())[:5]):
        x = 77 + i*54
        d.rounded_rectangle((x,252,x+38,267), radius=7, fill=c)
    chats = [("Mina","Sent you a photo"),("Design group","That palette is clean"),
             ("Saved Messages","Theme concept"),("Spike","Looks good ✓")]
    y = 292
    for idx, (name, sub) in enumerate(chats):
        if idx == 0:
            d.rounded_rectangle((66,y-7,378,y+66), radius=16, fill=colors["chat_inBubble"])
        d.ellipse((78,y+2,119,y+43), fill=blend(accent,bg,0.25))
        d.ellipse((91,y+13,106,y+28), fill=accent)
        d.text((132,y+1), name, font=font(16, True), fill=text)
        d.text((132,y+27), sub, font=font(12), fill=hint)
        y += 88
    d.rounded_rectangle((410,166,1046,697), radius=22, fill=bg)
    d.rounded_rectangle((410,166,1046,230), radius=22, fill=panel)
    d.text((438,184), "Spike Theme Preview", font=font(19, True), fill=text)
    d.text((438,209), "online", font=font(12), fill=hint)
    if image_bytes:
        try:
            with Image.open(io.BytesIO(image_bytes)) as src:
                wallpaper = src.convert("RGB")
                wallpaper.thumbnail((610,400))
                wallpaper = ImageEnhance.Brightness(wallpaper).enhance(0.30 if mode == "dark" else 0.18)
                wallpaper = wallpaper.filter(ImageFilter.GaussianBlur(2))
                wallpaper = ImageEnhance.Color(wallpaper).enhance(0.7)
                tile = Image.new("RGB",(610,400),bg)
                tile.paste(wallpaper,((610-wallpaper.width)//2,(400-wallpaper.height)//2))
                im.paste(tile,(420,240))
                overlay = Image.new("RGBA",(610,400),(*bg,105))
                im.paste(overlay,(420,240),overlay)
                d = ImageDraw.Draw(im)
        except Exception:
            pass
    d.rounded_rectangle((445,274,690,337), radius=17, fill=incoming)
    d.text((462,288),"The colors fit perfectly.",font=font(14),fill=colors["chat_messageTextIn"])
    d.text((462,314),"09:41",font=font(10),fill=hint)
    d.rounded_rectangle((690,355,1008,424), radius=17, fill=outgoing)
    d.text((708,371),"A custom theme for this image.",font=font(14),fill=colors["chat_messageTextOut"])
    d.text((708,399),"09:42   ✓✓",font=font(10),fill=colors["chat_messageTextOut"])
    d.rounded_rectangle((455,448,735,507), radius=17, fill=incoming)
    d.text((472,462),"Wallpaper + matching palette",font=font(13),fill=colors["chat_messageTextIn"])
    d.text((472,486),"09:42",font=font(10),fill=hint)
    d.rounded_rectangle((435,624,1022,677), radius=22, fill=panel)
    d.text((458,642),"Message",font=font(14),fill=hint)
    d.rounded_rectangle((962,633,1010,670), radius=18, fill=accent)
    d.text((976,640),"➤",font=font(19,True),fill=(255,255,255))
    return im

def menu(user_id):
    rows = [
        [InlineKeyboardButton("🎨 ساخت تم جدید", callback_data="new")],
        [InlineKeyboardButton("🌙 تیره", callback_data="mode:dark"),
         InlineKeyboardButton("☀️ روشن", callback_data="mode:light")],
        [InlineKeyboardButton("🎛 سبک و رنگ‌بندی", callback_data="styles"),
         InlineKeyboardButton("📖 راهنما", callback_data="help")],
    ]
    if OWNER_ID and user_id == OWNER_ID:
        rows.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin")])
    return InlineKeyboardMarkup(rows)

def styles_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("متعادل", callback_data="style:balanced"),
         InlineKeyboardButton("پررنگ", callback_data="style:vivid")],
        [InlineKeyboardButton("ملایم", callback_data="style:soft"),
         InlineKeyboardButton("مینیمال", callback_data="style:minimal")],
        [InlineKeyboardButton("↩️ منوی اصلی", callback_data="home")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user(update.effective_user)
    context.user_data.setdefault("mode", "dark")
    context.user_data.setdefault("style", "balanced")
    await update.effective_message.reply_text(
        "✦ SPIKE THEME STUDIO\n\n"
        "از والپیپرت یک تم رنگی اختصاصی بساز.\n"
        "اسم پروژه، حالت روشن/تیره و سبک را انتخاب کن؛ بعد عکس را بفرست تا فایل تم، "
        "پیش‌نمایش و والپیپر جداگانه بگیری.\n\nبرای شروع دکمهٔ ساخت تم جدید را بزن.",
        reply_markup=menu(update.effective_user.id))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("لغو شد.", reply_markup=menu(update.effective_user.id))
    return ConversationHandler.END

async def begin_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    record_user(update.effective_user)
    await q.message.reply_text("اسم پروژهٔ تم رو بفرست.\nمثلاً: Neon Rain یا Spike Ocean\n\nلغو: /cancel")
    return WAIT_NAME

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record_user(update.effective_user)
    await update.effective_message.reply_text("اسم پروژهٔ تم رو بفرست:\nلغو: /cancel")
    return WAIT_NAME

async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["project_name"] = safe_name(update.effective_message.text or "")
    await update.effective_message.reply_text(
        f"اسم پروژه ثبت شد: {context.user_data['project_name']}\n\n"
        "حالا والپیپر رو به‌صورت عکس (Photo) بفرست.\n"
        f"حالت: {'تیره' if context.user_data.get('mode','dark') == 'dark' else 'روشن'} | "
        f"سبک: {STYLES.get(context.user_data.get('style','balanced'), STYLES['balanced'])[0]}")
    return WAIT_PHOTO

async def got_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    uid = update.effective_user.id
    try:
        if not msg or not msg.photo:
            await msg.reply_text("عکس رو با گزینهٔ Photo بفرست.")
            return WAIT_PHOTO
        await msg.reply_text("🔬 دارم رنگ‌های تصویر رو تحلیل می‌کنم و پیش‌نمایش می‌سازم…")
        tgfile = await msg.photo[-1].get_file()
        buf = io.BytesIO()
        await tgfile.download_to_memory(out=buf)
        image_bytes = buf.getvalue()
        if len(image_bytes) > 12 * 1024 * 1024:
            await msg.reply_text("این تصویر برای هاست رایگان خیلی بزرگه؛ نسخهٔ کم‌حجم‌ترش رو بفرست.")
            return ConversationHandler.END
        with Image.open(io.BytesIO(image_bytes)) as test:
            if test.format not in ("JPEG", "PNG", "WEBP"):
                await msg.reply_text("فرمت عکس رو به JPG یا PNG تبدیل کن و دوباره بفرست.")
                return WAIT_PHOTO
            test.verify()
        palette = analyze_palette(image_bytes)
        mode = context.user_data.get("mode", "dark")
        style = context.user_data.get("style", "balanced")
        project = safe_name(context.user_data.get("project_name", "SpikeTheme"))
        colors = build_colors(palette, mode, style)
        theme_bytes = make_attheme(colors).encode("utf-8")
        preview = make_preview(image_bytes, colors, project, mode, style)
        preview_buf = io.BytesIO()
        preview.save(preview_buf, format="PNG", optimize=True)
        preview_buf.seek(0)
        await msg.reply_document(
            document=InputFile(io.BytesIO(theme_bytes), filename=f"{project}_{mode}.attheme"),
            caption=f"🎨 تم رنگی آماده شد: {project}\nحالت: {mode} | سبک: {STYLES.get(style, STYLES['balanced'])[0]}\n\n"
                    "در تلگرام اندروید فایل رو باز کن و گزینهٔ اعمال تم رو بزن. سازگاری همهٔ کلیدها به نسخهٔ تلگرام بستگی داره.")
        await msg.reply_photo(
            photo=InputFile(preview_buf, filename=f"{project}_preview.png"),
            caption="🖼 پیش‌نمایش گرافیکیِ تقریبی از رنگ‌بندی؛ این اسکرین‌شات واقعی تلگرام نیست.")
        await msg.reply_document(
            document=InputFile(io.BytesIO(image_bytes), filename=f"{project}_wallpaper"),
            caption="🌄 والپیپر اصلی جداگانه. برای پس‌زمینهٔ چت باید خودت آن را در تنظیمات تلگرام اعمال کنی.")
        record_theme(uid, project, mode, style)
        await msg.reply_text("تمام شد. از منو می‌تونی تم بعدی رو بسازی یا حالت و سبک رو تغییر بدی.",
                             reply_markup=menu(uid))
        return ConversationHandler.END
    except Exception as exc:
        log.exception("Theme creation failed")
        record_error(uid, repr(exc))
        await msg.reply_text("❌ ساخت تم ناموفق شد. یک عکس JPG یا PNG دیگه امتحان کن؛ اگر تکرار شد، Console هاست باید بررسی بشه.")
        return ConversationHandler.END

async def photo_outside_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("اول «🎨 ساخت تم جدید» رو بزن تا اسم پروژه ثبت بشه.",
                                              reply_markup=menu(update.effective_user.id))

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data, uid = q.data or "", update.effective_user.id
    record_user(update.effective_user)
    if data == "home":
        await q.message.reply_text("منوی اصلی:", reply_markup=menu(uid))
    elif data == "styles":
        await q.message.reply_text("سبک رنگ‌بندی رو انتخاب کن:", reply_markup=styles_keyboard())
    elif data.startswith("style:"):
        style = data.split(":", 1)[1]
        if style in STYLES:
            context.user_data["style"] = style
        await q.message.reply_text("سبک انتخاب شد: " + STYLES.get(style, STYLES["balanced"])[0],
                                   reply_markup=menu(uid))
    elif data.startswith("mode:"):
        mode = data.split(":", 1)[1]
        if mode in ("dark", "light"):
            context.user_data["mode"] = mode
        await q.message.reply_text("حالت انتخاب شد: " + ("تیره" if mode == "dark" else "روشن"),
                                   reply_markup=menu(uid))
    elif data == "help":
        await q.message.reply_text(
            "راهنما:\n۱) ساخت تم جدید\n۲) وارد کردن اسم پروژه\n۳) فرستادن والپیپر به‌صورت Photo\n"
            "۴) دریافت فایل .attheme، پیش‌نمایش و والپیپر\n\n"
            "ربات نمی‌تونه بدون اجازهٔ تو والپیپر یا تنظیمات گوشی رو تغییر بده.",
            reply_markup=menu(uid))
    elif data == "admin":
        if not OWNER_ID or uid != OWNER_ID:
            await q.message.reply_text("این بخش فقط برای مالک رباته.")
            return
        con = db()
        users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        themes = con.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
        errors = con.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
        recent = con.execute("SELECT project_name, mode, style, created_at FROM themes ORDER BY id DESC LIMIT 5").fetchall()
        con.close()
        recent_text = "\n".join(f"• {n} | {m} | {s} | {t[:10]}" for n,m,s,t in recent) or "هنوز تمی ساخته نشده."
        await q.message.reply_text(
            f"👑 پنل مدیریت\n\nکاربران ثبت‌شده: {users}\nتم‌های ساخته‌شده: {themes}\nخطاهای ثبت‌شده: {errors}\n\nآخرین تم‌ها:\n{recent_text}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ منوی اصلی", callback_data="home")]]))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled bot exception", exc_info=context.error)

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")
    db().close()
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("new", new_command),
                      CallbackQueryHandler(begin_new, pattern="^new$")],
        states={
            WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            WAIT_PHOTO: [MessageHandler(filters.PHOTO, got_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, photo_outside_flow))
    app.add_error_handler(error_handler)
    log.info("Spike Theme Studio starting; owner configured=%s", bool(OWNER_ID))
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
