import os
import re
import asyncio
import logging
import yt_dlp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ================== الإعدادات ==================

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

ARABIC_VOICES = {
    "male": "ar-SA-HamedNeural",
    "female": "ar-SA-ZariyahNeural"
}

ENGLISH_VOICES = {
    "male": "en-US-GuyNeural",
    "female": "en-US-JennyNeural"
}

user_texts = {}
user_videos = {}
DOWNLOAD_QUEUE = asyncio.Queue()

# ================== أدوات مساعدة ==================

def extract_url(text):
    m = re.search(r"https?://\S+", text)
    return m.group(0) if m else None

def detect_language(text: str):
    ar = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    en = sum(1 for c in text if c.isascii() and c.isalpha())
    return "ar" if ar >= en else "en"

def normalize_sudanese_arabic(text: str):
    replacements = {
        "داير": "أريد",
        "عايز": "أريد",
        "خلي": "اجعل",
        "سمعني": "اقرأ لي",
        "دا": "هذا",
        "دي": "هذه",
        "شنو": "ما"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def detect_tts_intent(text: str):
    triggers = [
        "حول النص الى صوت",
        "اقرأ لي",
        "سمعني",
        "داير اسمع"
    ]
    for t in triggers:
        if t in text:
            return text.replace(t, "").strip()
    return None

# ================== أحداث البوت ==================

async def on_startup(app: Application):
    app.bot_data["loop"] = asyncio.get_running_loop()
    app.create_task(download_worker(app))
    try:
        await app.bot.send_message(
            chat_id=ADMIN_ID,
            text="تم تشغيل البوت بنجاح على Railway"
        )
    except:
        pass

async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"خطأ في البوت:\n{context.error}"
        )
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أرسل نص لتحويله لصوت أو رابط فيديو للتحميل"
    )

# ================== التحميل ==================

async def inspect_video(update, context, url):
    msg = await update.message.reply_text("جاري فحص الرابط...")
    try:
        info = await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL({"quiet": True}).extract_info(url, download=False)
        )
    except Exception as e:
        await msg.edit_text(f"خطأ: {e}")
        return

    user_videos[update.effective_user.id] = url
    kb = [
        [InlineKeyboardButton("360p", callback_data="dl_360"),
         InlineKeyboardButton("720p", callback_data="dl_720")],
        [InlineKeyboardButton("MP3", callback_data="dl_audio")]
    ]
    await msg.edit_text(
        f"{info.get('title','Video')}\nاختر الجودة",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def download_worker(app: Application):
    loop = app.bot_data["loop"]
    while True:
        job = await DOWNLOAD_QUEUE.get()
        chat_id, url, q = job.values()

        fmt = {
            "dl_360": "bestvideo[height<=360]+bestaudio/best",
            "dl_720": "bestvideo[height<=720]+bestaudio/best",
            "dl_audio": "bestaudio"
        }[q]

        out = f"job_{chat_id}.%(ext)s"
        opts = {"format": fmt, "outtmpl": out, "quiet": True}

        if q == "dl_audio":
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3"
            }]

        try:
            await asyncio.to_thread(
                lambda: yt_dlp.YoutubeDL(opts).download([url])
            )
            file = next(f for f in os.listdir(".") if f.startswith(f"job_{chat_id}"))
            with open(file, "rb") as f:
                await app.bot.send_document(chat_id, f)
            os.remove(file)
        except Exception as e:
            await app.bot.send_message(chat_id, f"فشل التحميل: {e}")

# ================== الأزرار ==================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data.startswith("dl_"):
        url = user_videos.get(uid)
        await q.edit_message_text("تمت إضافة التحميل")
        await DOWNLOAD_QUEUE.put({
            "chat_id": q.message.chat_id,
            "url": url,
            "quality": q.data
        })

# ================== الرد الذكي ==================

async def smart_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    tts = detect_tts_intent(text)
    if tts:
        text = normalize_sudanese_arabic(tts)
        lang = detect_language(text)
        user_texts[update.effective_user.id] = {
            "text": text,
            "lang": lang
        }

        kb = [[
            InlineKeyboardButton("ذكر", callback_data=f"{lang}_male"),
            InlineKeyboardButton("أنثى", callback_data=f"{lang}_female")
        ]]
        await update.message.reply_text(
            "اختر الصوت",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    url = extract_url(text)
    if url:
        await inspect_video(update, context, url)
        return

    await update.message.reply_text(text)

# ================== التشغيل ==================

def main():
    app = Application.builder().token(TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, smart_reply))
    app.add_error_handler(error_handler)

    print("البوت يعمل")
    app.run_polling()

if __name__ == "__main__":
    main()
