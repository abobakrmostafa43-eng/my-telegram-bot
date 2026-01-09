import logging
import os
import yt_dlp
import edge_tts
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# التوكن الخاص بك
TOKEN = "8304502500:AAHA11xiInilFSKHJB5VtrYSS5qCnq2td98"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- كود خداع ريندر (لإبقاء الخدمة المجانية حية) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running")

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()
# --------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"أهلاً بك! 🌟\nأرسل رابطاً للتحميل أو نصاً لتحويله لصوت.")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith('http'):
        context.user_data['link'] = text
        keyboard = [[InlineKeyboardButton("🎬 تحميل الفيديو", callback_query_data='dl_vid')]]
        await update.message.reply_text("رابط فيديو! اضغط للتحميل:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        context.user_data['txt'] = text
        keyboard = [[InlineKeyboardButton("👨 ذكر", callback_query_data='v_m'), 
                     InlineKeyboardButton("👩 أنثى", callback_query_data='v_f')]]
        await update.message.reply_text("نص عادي! اختر نوع الصوت:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        msg = await query.edit_message_text("⏳ جاري التحميل...")
        ydl_opts = {'format': 'best', 'outtmpl': 'video.%(ext)s'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(context.user_data['link'], download=True)
            f = ydl.prepare_filename(info)
        await context.bot.send_video(chat_id=query.message.chat_id, video=open(f, 'rb'))
        os.remove(f)
        await msg.delete()

if __name__ == '__main__':
    # تشغيل خادم الويب الوهمي في خلفية الكود لإرضاء Render
    threading.Thread(target=run_health_check, daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    app.run_polling()
