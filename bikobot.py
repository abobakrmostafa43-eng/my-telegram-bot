import logging
import os
import yt_dlp
import edge_tts
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# ضع التوكن الخاص بك هنا
TOKEN = "8304502500:AAHA11xiInilFSKHJB5VtrYSS5qCnq2td98"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# دالة الترحيب والبداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"أهلاً بك يا {user_name}! 🌟\n\n"
        "أنا بوتك الذكي والمطور:\n"
        "📥 للتحميل: أرسل أي رابط فيديو.\n"
        "🎙 للصوت: أرسل أي نص وسأحوله لك."
    )

# دالة التعامل مع الرسائل (رابط أو نص)
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # إذا كان رابطاً
    if text.startswith(('http', 'www')):
        context.user_data['url'] = text
        keyboard = [
            [InlineKeyboardButton("🎬 فيديو (أعلى جودة)", callback_query_data='vid_high')],
            [InlineKeyboardButton("🎬 فيديو (جودة متوسطة)", callback_query_data='vid_low')],
            [InlineKeyboardButton("🎵 صوت فقط (MP3)", callback_query_data='aud_only')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("اختر الجودة المطلوبة للتحميل:", reply_markup=reply_markup)
    
    # إذا كان نصاً عادياً
    else:
        context.user_data['text'] = text
        keyboard = [
            [InlineKeyboardButton("🎙 صوت رجل (فخم)", callback_query_data='voice_m')],
            [InlineKeyboardButton("🎙 صوت امرأة (ناعم)", callback_query_data='voice_f')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("وصلني نصك! اختر نوع الصوت المفضل:", reply_markup=reply_markup)

# معالجة ضغطات الأزرار (تحميل أو صوت)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # أولاً: معالجة تحويل النص لصوت
    if data.startswith('voice_'):
        text = context.user_data.get('text')
        voice = "ar-SA-HamedNeural" if data == 'voice_m' else "ar-SA-ZariyahNeural"
        await query.edit_message_text("⏳ جاري إنشاء الملف الصوتي...")
        
        output = f"voice_{query.from_user.id}.mp3"
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output)
            await context.bot.send_voice(chat_id=query.message.chat_id, voice=open(output, 'rb'))
            os.remove(output)
            await query.message.delete()
        except Exception as e:
            await query.edit_message_text(f"خطأ في الصوت: {str(e)}")

    # ثانياً: معالجة تحميل الفيديو
    elif data.startswith(('vid_', 'aud_')):
        url = context.user_data.get('url')
        await query.edit_message_text("🚀 جاري التحميل.. قد يستغرق الأمر لحظات حسب حجم الفيديو.")
        
        format_opt = 'best' if data == 'vid_high' else 'worst'
        if data == 'aud_only': format_opt = 'bestaudio'

        ydl_opts = {
            'format': format_opt,
            'outtmpl': f'file_{query.from_user.id}.%(ext)s',
            'quiet': True,
            'no_warnings': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
            
            if data == 'aud_only':
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(filename, 'rb'))
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=open(filename, 'rb'))
            
            os.remove(filename)
            await query.message.delete()
        except Exception as e:
            await query.edit_message_text(f"فشل التحميل: {str(e)}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_all_messages))
    
    application.run_polling()
