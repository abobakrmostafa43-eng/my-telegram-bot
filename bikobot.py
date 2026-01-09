import logging
import os
import yt_dlp
import edge_tts
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# توكن البوت الخاص بك
TOKEN = "8304502500:AAHA11xiInilFSKHJB5VtrYSS5qCnq2td98"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- كود إرضاء Render (خادم ويب وهمي) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Live and Stable!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()
# ---------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! البوت الآن مستقر تماماً ✅\nأرسل رابطاً للتحميل أو نصاً لتحويله لصوت.")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith(('http', 'www')):
        context.user_data['link'] = text
        keyboard = [[InlineKeyboardButton("🎬 تحميل الفيديو (جودة عالية)", callback_query_data='dl_vid')]]
        await update.message.reply_text("تم التعرف على الرابط 👇", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        context.user_data['txt'] = text
        keyboard = [[InlineKeyboardButton("👨 صوت ذكر", callback_query_data='v_m'), 
                     InlineKeyboardButton("👩 صوت أنثى", callback_query_data='v_f')]]
        await update.message.reply_text("اختر نوع الصوت المفضل:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('v_'):
        voice = "ar-SA-HamedNeural" if query.data == 'v_m' else "ar-SA-ZariyahNeural"
        msg = await query.edit_message_text("⏳ جاري التحويل...")
        out = f"v_{query.from_user.id}.mp3"
        await edge_tts.Communicate(context.user_data['txt'], voice).save(out)
        await context.bot.send_voice(chat_id=query.message.chat_id, voice=open(out, 'rb'))
        os.remove(out)
        await msg.delete()
        
    elif query.data == 'dl_vid':
        msg = await query.edit_message_text("🚀 جاري تحميل الفيديو...")
        ydl_opts = {'format': 'best', 'outtmpl': 'video.%(ext)s', 'quiet': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(context.user_data['link'], download=True)
                f = ydl.prepare_filename(info)
            await context.bot.send_video(chat_id=query.message.chat_id, video=open(f, 'rb'), caption="تم التحميل بنجاح ✅")
            os.remove(f)
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"خطأ: {str(e)}")

if __name__ == '__main__':
    # تشغيل خادم الصحة في خيط منفصل (Thread)
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    # تشغيل البوت
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    application.run_polling()
