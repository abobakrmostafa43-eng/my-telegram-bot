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

# الإعدادات الأساسية
TOKEN = "8562688558:AAEfh8nDd8WKQuaxmMIhMWMQPTby4skzy64"
ADMIN_ID = 1947672003  # ضع الـ ID الخاص بك

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الأصوات المحسّنة لـ edge_tts مع خيارات إضافية
ARABIC_VOICES = {
    'male': 'ar-SA-HamedNeural',
    'female': 'ar-SA-ZariyahNeural',
    'male2': 'ar-EG-ShakirNeural',  # صوت مصري ذكر
    'female2': 'ar-EG-SalmaNeural'   # صوت مصري أنثى
}

ENGLISH_VOICES = {
    'male': 'en-US-GuyNeural',
    'female': 'en-US-JennyNeural',
    'male2': 'en-GB-RyanNeural',      # صوت بريطاني ذكر
    'female2': 'en-GB-SoniaNeural'    # صوت بريطاني أنثى
}

# تخزين بيانات المستخدمين
user_texts = {}
user_videos = {}
DOWNLOAD_QUEUE = asyncio.Queue()

# دوال مساعدة

def extract_url(text):
    """استخراج الرابط من النص"""
    match = re.search(r'https?://\S+', text)
    return match.group(0) if match else None

def detect_language(text: str):
    """كشف لغة النص"""
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    return "ar" if arabic_chars >= english_chars else "en"

def normalize_sudanese_arabic(text: str):
    """تطبيع اللهجة السودانية إلى فصحى"""
    replacements = {
        "داير": "أريد", "عايز": "أريد", "خلّي": "اجعل", "خلي": "اجعل",
        "سمّعني": "اقرأ لي", "سمعني": "اقرأ لي", "اقرا لي": "اقرأ لي",
        "دا": "هذا", "دي": "هذه", "ديل": "هؤلاء", "كدا": "هكذا",
        "كده": "هكذا", "شنو": "ما", "شنو دا": "ما هذا", "زي": "مثل",
        "شايف": "أرى", "ماشي": "حسناً", "تمام": "حسناً", "كويس": "جيد"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def detect_tts_intent(text: str):
    """كشف نية تحويل النص إلى صوت"""
    text_lower = text.lower()
    triggers = [
        "حول النص الى صوت", "حوّل النص الى صوت", "حول النص لصوت",
        "اقرأ لي", "سمّعني", "عايز اسمع", "داير اسمع", "طلع صوت",
        "خلّي النص صوت", "خلّي دا صوت", "خلي النص صوت", "صوت من النص",
        "نص لصوت", "تحويل لصوت"
    ]
    for trigger in triggers:
        if trigger in text_lower:
            cleaned = text_lower.replace(trigger, "").strip(" :،")
            if cleaned:
                return cleaned
    return None

# معالجات الأوامر الأساسية

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    welcome_msg = """
مرحباً بك في bakry bot
الميزات المتاحة:

📝 تحويل النص إلى صوت
   - أرسل نص وسيتم تحويله تلقائياً
   - استخدم /voice للعربية
   - استخدم /voiceen للإنجليزية

📹 تحميل الفيديوهات
   - أرسل رابط الفيديو مباشرة
   - أو استخدم /download مع الرابط
   - جودات متعددة متاحة

للبدء، أرسل نص أو رابط فيديو
    """
    await update.message.reply_text(welcome_msg.strip())

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر تحميل الفيديو"""
    if not context.args:
        await update.message.reply_text("⚠️ الرجاء إرسال رابط الفيديو بعد الأمر")
        return
    url = context.args[0]
    await inspect_video(update, context, url)

async def inspect_video(update, context, url):
    """فحص الفيديو وعرض خيارات الجودة"""
    msg = await update.message.reply_text("🔍 جاري فحص الرابط...")
    
    def run_extract():
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            return ydl.extract_info(url, download=False)
    
    try:
        info = await asyncio.to_thread(run_extract)
    except Exception as e:
        await msg.edit_text(f"❌ خطأ في فحص الرابط:\n{str(e)[:200]}")
        logger.error(f"Video inspect error: {e}")
        return

    user_videos[update.effective_user.id] = url
    
    keyboard = [
        [
            InlineKeyboardButton("360p", callback_data="dl_360"),
            InlineKeyboardButton("480p", callback_data="dl_480")
        ],
        [
            InlineKeyboardButton("720p", callback_data="dl_720"),
            InlineKeyboardButton("1080p", callback_data="dl_1080")
        ],
        [
            InlineKeyboardButton("أفضل جودة", callback_data="dl_best")
        ],
        [
            InlineKeyboardButton("🎵 صوت MP3 فقط", callback_data="dl_audio")
        ]
    ]
    
    title = info.get('title', 'فيديو غير معروف')[:100]
    await msg.edit_text(
        f"📹 العنوان: {title}\n\n⬇️ اختر الجودة المطلوبة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أزرار الاختيار"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # معالجة تحميل الفيديو
    if query.data.startswith("dl_"):
        url = user_videos.get(user_id)
        if not url:
            await query.edit_message_text("❌ انتهت الجلسة، الرجاء المحاولة مرة أخرى")
            return
        
        await query.edit_message_text("⏳ تمت إضافة الطلب للطابور، سيتم التحميل قريباً...")
        await DOWNLOAD_QUEUE.put({
            "chat_id": query.message.chat_id,
            "url": url,
            "quality": query.data
        })

    # معالجة اختيار الصوت
    elif query.data.startswith(("ar_", "en_")):
        data = user_texts.get(user_id)
        if not data:
            await query.edit_message_text("❌ انتهت الجلسة")
            return
        
        lang, gender = query.data.split("_")
        if lang == "ar":
            voice = ARABIC_VOICES[gender]
        else:
            voice = ENGLISH_VOICES[gender]
        
        data["voice"] = voice
        user_texts[user_id] = data
        
        keyboard = [
            [
                InlineKeyboardButton("🎙️ رسالة صوتية", callback_data="out_voice"),
                InlineKeyboardButton("🎵 ملف MP3", callback_data="out_audio")
            ]
        ]
        await query.edit_message_text(
            "📤 اختر طريقة الإخراج:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # معالجة إخراج الصوت
    elif query.data in ("out_voice", "out_audio"):
        data = user_texts.pop(user_id, None)
        if not data:
            await query.edit_message_text("❌ انتهت الجلسة")
            return
        
        await query.edit_message_text("⏳ جاري تحويل النص إلى صوت...")
        
        mp3_file = f"tts_{query.message.message_id}.mp3"
        ogg_file = f"tts_{query.message.message_id}.ogg"
        
        import edge_tts
        
        try:
            # تحويل النص إلى صوت بجودة عالية
            communicate = edge_tts.Communicate(data["text"], data["voice"], rate="+0%", volume="+0%")
            await communicate.save(mp3_file)
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ في تحويل النص إلى صوت:\n{str(e)[:200]}")
            logger.error(f"TTS error: {e}")
            return

        try:
            if query.data == "out_voice":
                # تحويل إلى رسالة صوتية OGG
                cmd = f"ffmpeg -y -i {mp3_file} -c:a libopus -b:a 128k {ogg_file}"
                if os.system(cmd) != 0:
                    await query.edit_message_text("❌ خطأ في معالجة الصوت")
                    return
                
                with open(ogg_file, "rb") as f:
                    await context.bot.send_voice(
                        query.message.chat_id,
                        voice=f,
                        caption="🎙️ رسالة صوتية جاهزة"
                    )
                
                if os.path.exists(ogg_file):
                    os.remove(ogg_file)
            else:
                # إرسال كملف MP3
                with open(mp3_file, "rb") as f:
                    await context.bot.send_audio(
                        query.message.chat_id,
                        audio=f,
                        title="تحويل النص إلى صوت",
                        caption="🎵 ملف MP3 جاهز"
                    )
            
            if os.path.exists(mp3_file):
                os.remove(mp3_file)
            
            await query.edit_message_text("✅ تم بنجاح")
            
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ في إرسال الملف:\n{str(e)[:200]}")
            logger.error(f"Send file error: {e}")

async def download_worker(app: Application):
    """عامل التحميل في الخلفية"""
    loop = app.bot_data["loop"]
    
    while True:
        job = await DOWNLOAD_QUEUE.get()
        chat_id = job["chat_id"]
        url = job["url"]
        quality = job["quality"]
        
        # تحديد صيغة الجودة
        format_map = {
            "dl_360": "bestvideo[height<=360]+bestaudio/best",
            "dl_480": "bestvideo[height<=480]+bestaudio/best",
            "dl_720": "bestvideo[height<=720]+bestaudio/best",
            "dl_1080": "bestvideo[height<=1080]+bestaudio/best",
            "dl_best": "best",
            "dl_audio": "bestaudio"
        }
        
        format_str = format_map.get(quality, "best")
        progress_msg = await app.bot.send_message(chat_id, "⏳ بدء التحميل 0%")
        
        def progress_hook(d):
            if d["status"] == "downloading":
                percent = d.get("_percent_str", "0%")
                asyncio.run_coroutine_threadsafe(
                    progress_msg.edit_text(f"⏳ جاري التحميل {percent}"),
                    loop
                )
        
        output_template = f"download_{chat_id}.%(ext)s"
        ydl_opts = {
            "format": format_str,
            "outtmpl": output_template,
            "quiet": True,
            "progress_hooks": [progress_hook]
        }
        
        if quality == "dl_audio":
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320"  # جودة أعلى للصوت
            }]
        
        def run_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        
        try:
            await asyncio.to_thread(run_download)
            
            downloaded_file = next(
                f for f in os.listdir(".")
                if f.startswith(f"download_{chat_id}")
            )
            
            await progress_msg.edit_text("📤 جاري رفع الملف...")
            
            with open(downloaded_file, "rb") as f:
                await app.bot.send_document(
                    chat_id,
                    document=f,
                    caption="✅ تم التحميل بنجاح"
                )
            
            os.remove(downloaded_file)
            await progress_msg.delete()
            
        except Exception as e:
            await app.bot.send_message(
                chat_id,
                f"❌ فشل التحميل:\n{str(e)[:200]}"
            )
            logger.error(f"Download error: {e}")

async def smart_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج ذكي للرسائل النصية"""
    text = update.message.text.strip()
    
    # فحص نية تحويل النص إلى صوت
    tts_text = detect_tts_intent(text)
    if tts_text:
        normalized = normalize_sudanese_arabic(tts_text)
        lang = detect_language(normalized)
        user_id = update.effective_user.id
        
        user_texts[user_id] = {
            'text': normalized,
            'lang': lang
        }
        
        if lang == "ar":
            keyboard = [
                [
                    InlineKeyboardButton("🧔 ذكر سعودي", callback_data="ar_male"),
                    InlineKeyboardButton("👩 أنثى سعودية", callback_data="ar_female")
                ],
                [
                    InlineKeyboardButton("🧔 ذكر مصري", callback_data="ar_male2"),
                    InlineKeyboardButton("👩 أنثى مصرية", callback_data="ar_female2")
                ]
            ]
            await update.message.reply_text(
                '🎙️ اختر نوع الصوت:',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [
                [
                    InlineKeyboardButton("🧔 Male US", callback_data="en_male"),
                    InlineKeyboardButton("👩 Female US", callback_data="en_female")
                ],
                [
                    InlineKeyboardButton("🧔 Male UK", callback_data="en_male2"),
                    InlineKeyboardButton("👩 Female UK", callback_data="en_female2")
                ]
            ]
            await update.message.reply_text(
                '🎙️ Choose voice type:',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # فحص وجود رابط فيديو
    url = extract_url(text)
    if url:
        await inspect_video(update, context, url)
        return
    
    # رد عادي
    await update.message.reply_text(
        "أرسل نصاً لتحويله إلى صوت\nأو رابط فيديو لتحميله"
    )

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر تحويل نص عربي إلى صوت"""
    if not context.args:
        await update.message.reply_text('⚠️ الرجاء إرسال النص بعد الأمر')
        return
    
    text = ' '.join(context.args)
    user_texts[update.effective_user.id] = {'text': text, 'lang': 'ar'}
    
    keyboard = [
        [
            InlineKeyboardButton("🧔 ذكر سعودي", callback_data="ar_male"),
            InlineKeyboardButton("👩 أنثى سعودية", callback_data="ar_female")
        ],
        [
            InlineKeyboardButton("🧔 ذكر مصري", callback_data="ar_male2"),
            InlineKeyboardButton("👩 أنثى مصرية", callback_data="ar_female2")
        ]
    ]
    await update.message.reply_text(
        '🎙️ اختر نوع الصوت:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def voiceen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر تحويل نص إنجليزي إلى صوت"""
    if not context.args:
        await update.message.reply_text('⚠️ Please send text after the command')
        return
    
    text = ' '.join(context.args)
    user_texts[update.effective_user.id] = {'text': text, 'lang': 'en'}
    
    keyboard = [
        [
            InlineKeyboardButton("🧔 Male US", callback_data="en_male"),
            InlineKeyboardButton("👩 Female US", callback_data="en_female")
        ],
        [
            InlineKeyboardButton("🧔 Male UK", callback_data="en_male2"),
            InlineKeyboardButton("👩 Female UK", callback_data="en_female2")
        ]
    ]
    await update.message.reply_text(
        '🎙️ Choose voice type:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأخطاء العام"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    error_msg = f"⚠️ حدث خطأ تقني:\n\n{str(context.error)[:500]}"
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=error_msg
        )
    except Exception as e:
        logger.error(f"Failed to send error message to admin: {e}")

async def on_startup(app: Application):
    """دالة التشغيل"""
    app.bot_data["loop"] = asyncio.get_running_loop()
    app.create_task(download_worker(app))
    
    try:
        await app.bot.send_message(
            chat_id=ADMIN_ID,
            text="✅ تم تشغيل البوت بنجاح"
        )
    except Exception as e:
        logger.error(f"Startup notification error: {e}")

def main():
    """الدالة الرئيسية"""
    app = Application.builder().token(TOKEN).post_init(on_startup).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("download", download_command))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("voiceen", voiceen_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, smart_reply))
    
    # معالج الأخطاء
    app.add_error_handler(error_handler)
    
    logger.info("✅ البوت جاهز للعمل")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
