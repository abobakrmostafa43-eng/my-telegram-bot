from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import asyncio, os, re, yt_dlp, logging

# --- الإعدادات ---
TOKEN = "8304502500:AAHjoPk63bipkWzwmMMIcZzj5bFC46KPEJ8"
ADMIN_ID = 1947672003  # ضع ID الخاص بك
WEBHOOK_URL = "https://your-app-name.onrender.com"  # ⚠️ غيّر هذا لرابط Render الخاص بك

# Flask App
app = Flask(__name__)

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# الأصوات
ARABIC_VOICES = {'male': 'ar-SA-HamedNeural', 'female': 'ar-SA-ZariyahNeural'}
ENGLISH_VOICES = {'male': 'en-US-GuyNeural', 'female': 'en-US-JennyNeural'}

user_texts = {}
user_videos = {}
DOWNLOAD_QUEUE = asyncio.Queue()

# --- وظائف البوت (نفس الكود القديم) ---

def extract_url(text):
    m = re.search(r'https?://\S+', text)
    return m.group(0) if m else None

def detect_language(text: str):
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    return "ar" if arabic_chars >= english_chars else "en"

def normalize_sudanese_arabic(text: str):
    replacements = {
        "داير": "أريد", "عايز": "أريد", "خلّي": "اجعل", "خلي": "اجعل",
        "سمّعني": "اقرأ لي", "سمعني": "اقرأ لي", "اقرا لي": "اقرأ لي",
        "دا": "هذا", "دي": "هذه", "ديل": "هؤلاء", "كدا": "هكذا",
        "كده": "هكذا", "شنو": "ما", "شنو دا": "ما هذا"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def detect_tts_intent(text: str):
    text_lower = text.lower()
    triggers = [
        "حول النص الى صوت", "حوّل النص الى صوت", "حول النص لصوت",
        "اقرأ لي", "سمّعني", "عايز اسمع", "داير اسمع", "طلع صوت",
        "خلّي النص صوت", "خلّي دا صوت", "خلي النص صوت"
    ]
    for t in triggers:
        if t in text_lower:
            cleaned = text_lower.replace(t, "").strip(" :،")
            if cleaned: return cleaned
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت شغال على Render بنظام Webhook!\nأرسل نص لتحويله لصوت أو رابط فيديو للتحميل.")

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("أرسل رابط الفيديو")
        return
    await inspect_video(update, context, context.args[0])

async def inspect_video(update, context, url):
    msg = await update.message.reply_text("جاري فحص الرابط...")
    def run():
        with yt_dlp.YoutubeDL({"quiet": True}) as y:
            return y.extract_info(url, download=False)
    try:
        info = await asyncio.to_thread(run)
    except Exception as e:
        await msg.edit_text(f"❌ خطأ بفحص الرابط: {e}")
        return

    user_videos[update.effective_user.id] = url
    kb = [
        [InlineKeyboardButton("360p", callback_data="dl_360"),
         InlineKeyboardButton("480p", callback_data="dl_480")],
        [InlineKeyboardButton("720p", callback_data="dl_720"),
         InlineKeyboardButton("أفضل جودة", callback_data="dl_best")],
        [InlineKeyboardButton("MP3 صوت فقط", callback_data="dl_audio")]
    ]
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    await msg.edit_text(f"📹 {info.get('title', 'Video')}\nاختر الجودة:", reply_markup=InlineKeyboardMarkup(kb))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    if q.data.startswith("dl_"):
        url = user_videos.get(user_id)
        if not url:
            await q.edit_message_text("❌ انتهت الجلسة")
            return
        await q.edit_message_text("تمت إضافة التحميل للطابور، انتظر قليلاً...")
        await DOWNLOAD_QUEUE.put({"chat_id": q.message.chat_id, "url": url, "quality": q.data})

    elif q.data.startswith(("ar_", "en_")):
        data = user_texts.get(user_id)
        if not data:
            await q.edit_message_text("❌ انتهت الجلسة")
            return
        lang, gender = q.data.split("_")
        voice = ARABIC_VOICES[gender] if lang == "ar" else ENGLISH_VOICES[gender]
        data["voice"] = voice
        user_texts[user_id] = data
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        kb = [[InlineKeyboardButton("🎙️ تشغيل", callback_data="out_voice"),
               InlineKeyboardButton("🎵 تنزيل MP3", callback_data="out_audio")]]
        await q.edit_message_text("اختر طريقة الإخراج:", reply_markup=InlineKeyboardMarkup(kb))

    elif q.data in ("out_voice", "out_audio"):
        data = user_texts.pop(user_id, None)
        if not data:
            await q.edit_message_text("❌ انتهت الجلسة")
            return
        mp3 = f"tts_{q.message.message_id}.mp3"
        ogg = f"tts_{q.message.message_id}.ogg"
        import edge_tts
        try:
            await edge_tts.Communicate(data["text"], data["voice"]).save(mp3)
        except Exception as e:
            await q.edit_message_text(f"❌ خطأ في تحويل الصوت: {e}")
            return

        if q.data == "out_voice":
            cmd = f"ffmpeg -y -i {mp3} -c:a libopus {ogg}"
            if os.system(cmd) != 0:
                await q.edit_message_text("❌ خطأ في تحويل MP3 إلى OGG عبر ffmpeg")
                return
            try:
                with open(ogg, "rb") as f:
                    await context.bot.send_voice(q.message.chat_id, voice=f)
            except Exception as e:
                await q.edit_message_text(f"❌ خطأ في إرسال الصوت: {e}")
                return
            finally:
                if os.path.exists(ogg): os.remove(ogg)
        else:
            try:
                with open(mp3, "rb") as f:
                    await context.bot.send_audio(q.message.chat_id, audio=f, title="Text to Speech", caption="🎵 MP3 جاهز")
            except Exception as e:
                await q.edit_message_text(f"❌ خطأ في إرسال MP3: {e}")
                return
        if os.path.exists(mp3): os.remove(mp3)
        await q.edit_message_text("✅ تم بنجاح")

async def download_worker(application: Application):
    while True:
        job = await DOWNLOAD_QUEUE.get()
        chat_id, url, q = job["chat_id"], job["url"], job["quality"]
        fmt = {"dl_360": "bestvideo[height<=360]+bestaudio/best", 
               "dl_480": "bestvideo[height<=480]+bestaudio/best",
               "dl_720": "bestvideo[height<=720]+bestaudio/best", 
               "dl_best": "best", 
               "dl_audio": "bestaudio"}[q]
        progress_msg = await application.bot.send_message(chat_id, "بدء التحميل 0%")
        
        out = f"job_{chat_id}.%(ext)s"
        ydl_opts = {"format": fmt, "outtmpl": out, "quiet": True}
        if q == "dl_audio":
            ydl_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
        
        def run():
            with yt_dlp.YoutubeDL(ydl_opts) as y: 
                y.download([url])
        
        try:
            await asyncio.to_thread(run)
            file = next(f for f in os.listdir(".") if f.startswith(f"job_{chat_id}"))
            with open(file, "rb") as f: 
                await application.bot.send_document(chat_id, document=f)
            os.remove(file)
            await progress_msg.edit_text("✅ تم الإرسال")
        except Exception as e:
            await application.bot.send_message(chat_id, f"❌ فشل التحميل: {e}")

async def smart_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    tts_text = detect_tts_intent(text)
    if tts_text:
        normalized = normalize_sudanese_arabic(tts_text)
        lang = detect_language(normalized)
        user_id = update.effective_user.id
        user_texts[user_id] = {'text': normalized, 'lang': lang}
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        if lang == "ar":
            kb = [[InlineKeyboardButton("🧔 ذكر", callback_data="ar_male"), 
                   InlineKeyboardButton("👩 أنثى", callback_data="ar_female")]]
            await update.message.reply_text('اختر الصوت:', reply_markup=InlineKeyboardMarkup(kb))
        else:
            kb = [[InlineKeyboardButton("🧔 Male", callback_data="en_male"), 
                   InlineKeyboardButton("👩 Female", callback_data="en_female")]]
            await update.message.reply_text('Choose voice:', reply_markup=InlineKeyboardMarkup(kb))
        return
    url = extract_url(text)
    if url:
        await inspect_video(update, context, url)
        return
    await update.message.reply_text(text)

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('❌ أرسل نص')
        return
    text = ' '.join(context.args)
    user_texts[update.effective_user.id] = {'text': text, 'lang': 'ar'}
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    kb = [[InlineKeyboardButton("🧔 ذكر", callback_data="ar_male"), 
           InlineKeyboardButton("👩 أنثى", callback_data="ar_female")]]
    await update.message.reply_text('اختر الصوت:', reply_markup=InlineKeyboardMarkup(kb))

async def voiceen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('❌ Send text')
        return
    text = ' '.join(context.args)
    user_texts[update.effective_user.id] = {'text': text, 'lang': 'en'}
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    kb = [[InlineKeyboardButton("🧔 Male", callback_data="en_male"), 
           InlineKeyboardButton("👩 Female", callback_data="en_female")]]
    await update.message.reply_text('Choose voice:', reply_markup=InlineKeyboardMarkup(kb))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """صائد الأخطاء"""
    error_msg = f"⚠️ حدث خطأ:\n\n<code>{context.error}</code>"
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=error_msg, parse_mode='HTML')
    except:
        pass
    logging.error(f"Exception: {context.error}")

# --- إعداد Webhook ---
async def setup_application():
    """إعداد البوت مع Webhook"""
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("download", download_command))
    application.add_handler(CommandHandler("voice", voice_command))
    application.add_handler(CommandHandler("voiceen", voiceen_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, smart_reply))
    application.add_error_handler(error_handler)
    
    # بدء عامل التحميل
    asyncio.create_task(download_worker(application))
    
    # إرسال إشعار التشغيل
    try:
        await application.bot.send_message(chat_id=ADMIN_ID, text="🚀 البوت شغال على Render بنظام Webhook!")
    except:
        pass
    
    await application.initialize()
    await application.start()
    
    # ضبط الـ webhook
    webhook_url = f"{WEBHOOK_URL}/{TOKEN}"
    await application.bot.set_webhook(url=webhook_url)
    
    return application

# متغير عام للـ application
bot_app = None

@app.route('/')
def index():
    return "✅ Bot is running on Webhook mode!"

@app.route(f'/{TOKEN}', methods=['POST'])
async def webhook():
    """استقبال التحديثات من Telegram"""
    global bot_app
    if bot_app is None:
        return "Bot not initialized", 503
    
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    await bot_app.update_queue.put(update)
    return "OK"

# --- تشغيل البوت ---
if __name__ == '__main__':
    # إعداد البوت
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_app = loop.run_until_complete(setup_application())
    
    # تشغيل Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
