TOKEN = "8304502500:AAFXdEo2YKtDQIfrXgbkYirp50dcoFdj7vY"
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import asyncio, os, re, yt_dlp

# الأصوات لـ edge_tts
ARABIC_VOICES = {'male': 'ar-SA-HamedNeural', 'female': 'ar-SA-ZariyahNeural'}
ENGLISH_VOICES = {'male': 'en-US-GuyNeural', 'female': 'en-US-JennyNeural'}

user_texts = {}
user_videos = {}
DOWNLOAD_QUEUE = asyncio.Queue()

def extract_url(text):
    m = re.search(r'https?://\S+', text)
    return m.group(0) if m else None

def detect_language(text: str):
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    return "ar" if arabic_chars >= english_chars else "en"

def normalize_sudanese_arabic(text: str):
    replacements = {
        "داير": "أريد",
        "عايز": "أريد",
        "خلّي": "اجعل",
        "خلي": "اجعل",
        "سمّعني": "اقرأ لي",
        "سمعني": "اقرأ لي",
        "اقرا لي": "اقرأ لي",
        "دا": "هذا",
        "دي": "هذه",
        "ديل": "هؤلاء",
        "كدا": "هكذا",
        "كده": "هكذا",
        "شنو": "ما",
        "شنو دا": "ما هذا"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def detect_tts_intent(text: str):
    text_lower = text.lower()
    triggers = [
        "حول النص الى صوت",
        "حوّل النص الى صوت",
        "حول النص لصوت",
        "اقرأ لي",
        "سمّعني",
        "عايز اسمع",
        "داير اسمع",
        "طلع صوت",
        "خلّي النص صوت",
        "خلّي دا صوت",
        "خلي النص صوت"
    ]
    for t in triggers:
        if t in text_lower:
            # إزالة الترجر والحصول على النص المتبقي
            cleaned = text_lower.replace(t, "").strip(" :،")
            if cleaned:  # تأكد أن في نص بعد الترجر
                return cleaned
    return None

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت شغال. أرسل نص لتحويله لصوت أو رابط فيديو للتحميل.")

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
    await msg.edit_text(
        f"📹 {info.get('title', 'Video')}\nاختر الجودة:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    # معالجة تحميل الفيديو
    if q.data.startswith("dl_"):
        url = user_videos.get(user_id)
        if not url:
            await q.edit_message_text("❌ انتهت الجلسة")
            return

        await q.edit_message_text("تمت إضافة التحميل للطابور، انتظر قليلاً...")

        await DOWNLOAD_QUEUE.put({
            "chat_id": q.message.chat_id,
            "url": url,
            "quality": q.data
        })

    # معالجة اختيار الصوت
    elif q.data.startswith(("ar_", "en_")):
        data = user_texts.get(user_id)
        if not data:
            await q.edit_message_text("❌ انتهت الجلسة")
            return
        lang, gender = q.data.split("_")
        voice = ARABIC_VOICES[gender] if lang == "ar" else ENGLISH_VOICES[gender]
        data["voice"] = voice
        user_texts[user_id] = data
        kb = [[
            InlineKeyboardButton("🎙️ تشغيل", callback_data="out_voice"),
            InlineKeyboardButton("🎵 تنزيل MP3", callback_data="out_audio")
        ]]
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
                if os.path.exists(ogg):
                    os.remove(ogg)
        else:
            try:
                with open(mp3, "rb") as f:
                    await context.bot.send_audio(
                        q.message.chat_id,
                        audio=f,
                        title="Text to Speech",
                        caption="🎵 MP3 جاهز"
                    )
            except Exception as e:
                await q.edit_message_text(f"❌ خطأ في إرسال MP3: {e}")
                return

        if os.path.exists(mp3):
            os.remove(mp3)
        await q.edit_message_text("✅ تم بنجاح")

# عامل التحميل مع عرض نسبة التقدم
async def download_worker(app: Application):
    loop = app.bot_data["loop"]

    while True:
        job = await DOWNLOAD_QUEUE.get()
        chat_id = job["chat_id"]
        url = job["url"]
        q = job["quality"]

        fmt = {
            "dl_360": "bestvideo[height<=360]+bestaudio/best",
            "dl_480": "bestvideo[height<=480]+bestaudio/best",
            "dl_720": "bestvideo[height<=720]+bestaudio/best",
            "dl_best": "best",
            "dl_audio": "bestaudio"
        }[q]

        progress_msg = await app.bot.send_message(chat_id, "بدء التحميل 0%")

        def hook(d):
            if d["status"] == "downloading":
                percent = d.get("_percent_str", "0%")
                asyncio.run_coroutine_threadsafe(
                    progress_msg.edit_text(f"جاري التحميل {percent}"),
                    loop
                )

        out = f"job_{chat_id}.%(ext)s"

        ydl_opts = {
            "format": fmt,
            "outtmpl": out,
            "quiet": True,
            "progress_hooks": [hook]
        }

        if q == "dl_audio":
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]

        def run():
            with yt_dlp.YoutubeDL(ydl_opts) as y:
                y.download([url])

        try:
            await asyncio.to_thread(run)

            file = next(f for f in os.listdir(".") if f.startswith(f"job_{chat_id}"))

            with open(file, "rb") as f:
                await app.bot.send_document(chat_id, document=f)

            os.remove(file)
            await progress_msg.edit_text("✅ تم الإرسال")

        except Exception as e:
            await app.bot.send_message(chat_id, f"❌ فشل التحميل: {e}")

# رد ذكي للتعامل مع النصوص وروابط الفيديو والطلب الصوتي بدون أوامر
async def smart_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # تحقق من طلب تحويل النص لصوت (عامية وفصحى)
    tts_text = detect_tts_intent(text)
    if tts_text:
        normalized = normalize_sudanese_arabic(tts_text)
        lang = detect_language(normalized)
        
        # حفظ النص في user_texts مباشرة
        user_id = update.effective_user.id
        user_texts[user_id] = {'text': normalized, 'lang': lang}
        
        # اختيار الأزرار حسب اللغة
        if lang == "ar":
            kb = [[
                InlineKeyboardButton("🧔 ذكر", callback_data="ar_male"),
                InlineKeyboardButton("👩 أنثى", callback_data="ar_female")
            ]]
            await update.message.reply_text('اختر الصوت:', reply_markup=InlineKeyboardMarkup(kb))
        else:
            kb = [[
                InlineKeyboardButton("🧔 Male", callback_data="en_male"),
                InlineKeyboardButton("👩 Female", callback_data="en_female")
            ]]
            await update.message.reply_text('Choose voice:', reply_markup=InlineKeyboardMarkup(kb))
        return

    # لو النص فيه رابط، عالج تحميل الفيديو
    url = extract_url(text)
    if url:
        await inspect_video(update, context, url)
        return

    # لو لا، رد بنفس النص (ممكن تطور الردود الذكية لاحقًا)
    await update.message.reply_text(text)

# تنفيذ أوامر الصوت (للاستخدام المباشر مع الأوامر)
async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('❌ أرسل نص')
        return
    text = ' '.join(context.args)
    user_texts[update.effective_user.id] = {'text': text, 'lang': 'ar'}

    kb = [[
        InlineKeyboardButton("🧔 ذكر", callback_data="ar_male"),
        InlineKeyboardButton("👩 أنثى", callback_data="ar_female")
    ]]
    await update.message.reply_text('اختر الصوت:', reply_markup=InlineKeyboardMarkup(kb))

async def voiceen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('❌ Send text')
        return
    text = ' '.join(context.args)
    user_texts[update.effective_user.id] = {'text': text, 'lang': 'en'}

    kb = [[
        InlineKeyboardButton("🧔 Male", callback_data="en_male"),
        InlineKeyboardButton("👩 Female", callback_data="en_female")
    ]]
    await update.message.reply_text('Choose voice:', reply_markup=InlineKeyboardMarkup(kb))

async def on_startup(app: Application):
    app.bot_data["loop"] = asyncio.get_running_loop()
    app.create_task(download_worker(app))

def main():
    app = Application.builder().token(TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("download", download_command))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("voiceen", voiceen_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, smart_reply))

    print("✅ البوت شغال")
    app.run_polling()

if __name__ == "__main__":
    main()

