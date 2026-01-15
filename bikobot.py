from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import asyncio
import os
import re
import yt_dlp
import logging
import edge_tts  # تأكدت من استيرادها هنا بالأعلى

# 1. الإعدادات الأساسية - (تأكد من وضع التوكن والـ ID)
TOKEN = "8562688558:AAEfh8nDd8WKQuaxmMIhMWMQPTby4skzy64"
ADMIN_ID = 1947672003 # ضع الـ ID الحقيقي الخاص بك هنا كأرقام فقط

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الأصوات
ARABIC_VOICES = {
    'male': 'ar-SA-HamedNeural',
    'female': 'ar-SA-ZariyahNeural',
    'male2': 'ar-EG-ShakirNeural',
    'female2': 'ar-EG-SalmaNeural'
}

ENGLISH_VOICES = {
    'male': 'en-US-GuyNeural',
    'female': 'en-US-JennyNeural',
    'male2': 'en-GB-RyanNeural',
    'female2': 'en-GB-SoniaNeural'
}

# تخزين بيانات المستخدمين
user_texts = {}
user_videos = {}
DOWNLOAD_QUEUE = asyncio.Queue()

# --- الدوال المساعدة ---

def extract_url(text):
    match = re.search(r'https?://\S+', text)
    return match.group(0) if match else None

def detect_language(text: str):
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    return "ar" if arabic_chars >= english_chars else "en"

def normalize_sudanese_arabic(text: str):
    replacements = {
        "داير": "أريد", "عايز": "أريد", "شنو": "ماذا", "كدا": "هكذا", "دي": "هذه"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def detect_tts_intent(text: str):
    text_lower = text.lower()
    triggers = ["حول النص الى صوت", "اقرأ لي", "سمعني", "نص لصوت"]
    for trigger in triggers:
        if trigger in text_lower:
            cleaned = text_lower.replace(trigger, "").strip(" :،")
            return cleaned if cleaned else "مرحباً بك"
    return None

# --- المعالجات ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = "مرحباً بك في bakry bot\nأرسل نصاً لتحويله لصوت أو رابط فيديو لتحميله."
    await update.message.reply_text(welcome_msg)

async def inspect_video(update, context, url):
    msg = await update.message.reply_text("🔍 جاري فحص الرابط...")
    def run_extract():
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            return ydl.extract_info(url, download=False)
    try:
        info = await asyncio.to_thread(run_extract)
        user_videos[update.effective_user.id] = url
        keyboard = [[InlineKeyboardButton("360p", callback_data="dl_360"), InlineKeyboardButton("720p", callback_data="dl_720")],
                    [InlineKeyboardButton("🎵 MP3", callback_data="dl_audio")]]
        await msg.edit_text(f"📹 العنوان: {info.get('title', 'فيديو')[:50]}\nاختر الجودة:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {str(e)[:50]}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("dl_"):
        url = user_videos.get(user_id)
        if url:
            await query.edit_message_text("⏳ تمت إضافة الطلب للطابور...")
            await DOWNLOAD_QUEUE.put({"chat_id": query.message.chat_id, "url": url, "quality": query.data})

    elif query.data.startswith(("ar_", "en_")):
        data = user_texts.get(user_id)
        if data:
            lang, gender = query.data.split("_")
            data["voice"] = ARABIC_VOICES[gender] if lang == "ar" else ENGLISH_VOICES[gender]
            user_texts[user_id] = data
            keyboard = [[InlineKeyboardButton("🎙️ بصمة", callback_data="out_voice"), InlineKeyboardButton("🎵 MP3", callback_data="out_audio")]]
            await query.edit_message_text("📤 اختر طريقة الإخراج:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data in ("out_voice", "out_audio"):
        data = user_texts.pop(user_id, None)
        if data:
            await query.edit_message_text("⏳ جاري التحويل...")
            file_path = f"tts_{user_id}.mp3"
            try:
                communicate = edge_tts.Communicate(data["text"], data["voice"])
                await communicate.save(file_path)
                with open(file_path, "rb") as f:
                    if query.data == "out_voice":
                        await context.bot.send_voice(query.message.chat_id, voice=f)
                    else:
                        await context.bot.send_audio(query.message.chat_id, audio=f)
                os.remove(file_path)
            except Exception as e:
                await query.edit_message_text(f"❌ خطأ: {e}")

async def download_worker(app: Application):
    # تم إصلاح استدعاء loop هنا
    while True:
        job = await DOWNLOAD_QUEUE.get()
        chat_id = job["chat_id"]
        # منطق التحميل المبسط
        ydl_opts = {'format': 'best', 'outtmpl': f'dl_{chat_id}.%(ext)s', 'quiet': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.to_thread(ydl.download, [job["url"]])
            # إرسال الملف (تحتاج لإضافة منطق البحث عن الملف المرسل)
            await app.bot.send_message(chat_id, "✅ اكتمل التحميل (يرجى إضافة منطق إرسال الملفات)")
        except Exception as e:
            await app.bot.send_message(chat_id, f"❌ فشل: {e}")

async def smart_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    url = extract_url(text)
    if url:
        await inspect_video(update, context, url)
        return
    
    intent_text = detect_tts_intent(text)
    if intent_text or len(text) > 2:
        target_text = intent_text if intent_text else text
        user_texts[update.effective_user.id] = {'text': target_text}
        keyboard = [[InlineKeyboardButton("🧔 ذكر", callback_data="ar_male"), InlineKeyboardButton("👩 أنثى", callback_data="ar_female")]]
        await update.message.reply_text("🎙️ اختر نوع الصوت:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- الإصلاحات الجوهرية في التشغيل ---

async def post_init(app: Application):
    """دالة تبدأ بعد تشغيل البوت مباشرة"""
    asyncio.create_task(download_worker(app))
    try:
        await app.bot.send_message(chat_id=ADMIN_ID, text="✅ البوت يعمل الآن على PythonAnywhere")
    except:
        pass

def main():
    # 2. إصلاح TOKEN: تأكد أنه ليس فارغاً
    if not TOKEN:
        print("❌ خطأ: لم تضع TOKEN البوت!")
        return

    # 3. الطريقة الصحيحة لبناء التطبيق في الإصدار 20.x
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, smart_reply))
    
    print("✅ البوت شغال... اضغط Ctrl+C للإيقاف")
    # run_polling هي المسؤولة عن تشغيل الـ Event Loop داخلياً
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
