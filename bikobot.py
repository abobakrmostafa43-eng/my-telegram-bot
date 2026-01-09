import logging
import os
import yt_dlp
import edge_tts
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# ضع التوكن الخاص بك هنا
TOKEN = "8304502500:AAHA11xiInilFSKHJB5VtrYSS5qCnq2td98"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# دالة إعداد الأوامر تلقائياً في قائمة البوت
async def set_commands(application):
    commands = [
        BotCommand("start", "تشغيل البوت"),
        BotCommand("help", "طريقة الاستخدام")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"أهلاً بك يا {user_name}! 🌟\n\n"
        "أنا بوتك المتطور للتحميل وتحويل النصوص.\n"
        "📥 أرسل رابط فيديو (يوتيوب، فيسبوك، تيك توك) لتحميله بأعلى جودة.\n"
        "🎙 أرسل نصاً عادياً لتحويله لصوت بشري."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # فحص إذا كان الرابط فيديو
    if text.startswith(('http://', 'https://')):
        return await download_video(update, context)
    
    # إذا كان نصاً، نظهر أزرار اختيار الصوت (ذكر/أنثى)
    context.user_data['text_to_convert'] = text
    keyboard = [
        [
            InlineKeyboardButton("🎙 صوت رجل (فخم)", callback_query_data='male'),
            InlineKeyboardButton("🎙 صوت امرأة (ناعم)", callback_query_data='female')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر نوع الصوت المفضل لديك:", reply_markup=reply_markup)

async def voice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = context.user_data.get('text_to_convert', '')
    if not text:
        await query.edit_message_text("عذراً، أرسل النص مرة أخرى.")
        return

    voice = "ar-SA-HamedNeural" if query.data == 'male' else "ar-SA-ZariyahNeural"
    output = f"voice_{query.from_user.id}.mp3"

    await query.edit_message_text("⏳ جاري المعالجة بأعلى جودة...")

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output)
        await context.bot.send_voice(chat_id=query.message.chat_id, voice=open(output, 'rb'), caption="✅ تم التحويل بنجاح")
        os.remove(output)
        await query.message.delete()
    except Exception as e:
        await query.edit_message_text(f"خطأ: {str(e)}")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    msg = await update.message.reply_text("🚀 جاري سحب الفيديو بأعلى جودة ممكنة...")
    
    # إعدادات أعلى جودة للفيديو
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'video_file.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # التأكد من صيغة الملف بعد الدمج
            if not os.path.exists(filename):
                filename = filename.rsplit('.', 1)[0] + ".mp4"

        await msg.edit_text("📤 جاري الرفع...")
        await context.bot.send_video(chat_id=update.effective_chat.id, video=open(filename, 'rb'), caption=f"✅ تم التحميل: {info.get('title', '')}")
        os.remove(filename)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"حدث خطأ (ربما الفيديو خاص أو الرابط غير مدعوم): {str(e)}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    # تفعيل قائمة الأوامر تلقائياً
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_commands(application))

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(voice_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    application.run_polling()
