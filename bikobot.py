import logging
import os
import yt_dlp
import edge_tts
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# ضع التوكن الخاص بك هنا
TOKEN = "8304502500:AAHA11xiInilFSKHJB5VtrYSS5qCnq2td98"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(f"أهلاً بك يا {user_name}! 🌟\nأرسل رابطاً للتحميل أو نصاً لتحويله لصوت فخم.")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith(('http', 'www')):
        context.user_data['link'] = text
        keyboard = [[InlineKeyboardButton("🎬 تحميل فيديو بأفضل جودة", callback_query_data='dl_video')]]
        await update.message.reply_text("تم استلام الرابط:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        context.user_data['text_to_audio'] = text
        keyboard = [[InlineKeyboardButton("👨 ذكر (حامد)", callback_query_data='v_male'), 
                     InlineKeyboardButton("👩 أنثى (زارينا)", callback_query_data='v_female')]]
        await update.message.reply_text("اختر نوع الصوت المفضل لديك:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('v_'):
        voice = "ar-SA-HamedNeural" if query.data == 'v_male' else "ar-SA-ZariyahNeural"
        msg = await query.edit_message_text("⏳ جاري توليد صوت احترافي...")
        out = f"v_{query.from_user.id}.mp3"
        await edge_tts.Communicate(context.user_data['text_to_audio'], voice).save(out)
        await context.bot.send_voice(chat_id=query.message.chat_id, voice=open(out, 'rb'), caption="تم التحويل بأعلى جودة ✅")
        os.remove(out)
        await msg.delete()
    
    elif query.data == 'dl_video':
        msg = await query.edit_message_text("🚀 جاري التحميل... قد يستغرق وقتاً حسب الحجم.")
        ydl_opts = {'format': 'best', 'outtmpl': f'vid_{query.from_user.id}.%(ext)s', 'quiet': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(context.user_data['link'], download=True)
                filename = ydl.prepare_filename(info)
            await context.bot.send_video(chat_id=query.message.chat_id, video=open(filename, 'rb'), caption="تم التحميل بنجاح ✅")
            os.remove(filename)
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"خطأ في التحميل: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    app.run_polling()
