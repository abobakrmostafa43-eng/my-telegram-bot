import logging
import os
import yt_dlp
import edge_tts
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

TOKEN = "8304502500:AAHA11xiInilFSKHJB5VtrYSS5qCnq2td98"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# دالة البداية مع أزرار الخيارات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"أهلاً بك يا {user_name}! 🌟\n\n"
        "أنا بوتك المتطور. كيف يمكنني مساعدتك اليوم؟\n"
        "📥 أرسل رابط فيديو للتحميل.\n"
        "🎙 أرسل نصاً وسأعرض عليك خيارات الصوت."
    )

# دالة استقبال النص وعرض خيارات (ذكر/أنثى)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith(('http://', 'https://')):
        return await download_video(update, context)
    
    # حفظ النص مؤقتاً في ذاكرة البوت لاستخدامه بعد اختيار الصوت
    context.user_data['pending_text'] = text
    
    keyboard = [
        [
            InlineKeyboardButton("🎙 صوت ذكر (حامد)", callback_query_data='voice_male'),
            InlineKeyboardButton("🎙 صوت أنثى (زارينا)", callback_query_data='voice_female')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر نوع الصوت المفضل لديك:", reply_markup=reply_markup)

# معالجة اختيار الزر (ذكر أو أنثى)
async def voice_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = context.user_data.get('pending_text', '')
    if not text:
        await query.edit_message_text("عذراً، انتهت صلاحية النص. أرسله مرة أخرى.")
        return

    # اختيار المحرك بناءً على الضغطة
    voice = "ar-SA-HamedNeural" if query.data == 'voice_male' else "ar-SA-ZariyahNeural"
    output_file = f"voice_{query.from_user.id}.mp3"

    await query.edit_message_text("⏳ جاري توليد صوت بشري عالي الجودة...")

    try:
        # تحسين الجودة عبر ضبط السرعة والنبرة
        communicate = edge_tts.Communicate(text, voice, rate="+0%", pitch="+0Hz")
        await communicate.save(output_file)
        
        with open(output_file, 'rb') as audio:
            await context.bot.send_voice(chat_id=query.message.chat_id, voice=audio, caption="✅ تم التحويل بأفضل جودة متاحة.")
        
        os.remove(output_file)
        await query.message.delete()
    except Exception as e:
        await query.edit_message_text(f"خطأ تقني: {str(e)}")

# دالة التحميل
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    msg = await update.message.reply_text("🚀 جاري التحميل من المنصة...")
    ydl_opts = {'format': 'best', 'outtmpl': 'vid.%(ext)s', 'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
        await context.bot.send_video(chat_id=update.effective_chat.id, video=open(path, 'rb'))
        os.remove(path)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"فشل التحميل: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(voice_choice_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.run_polling()
