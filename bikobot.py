import logging
import os
import yt_dlp
import asyncio
import edge_tts
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ضع التوكن الخاص بك هنا
TOKEN = "8304502500:AAHA11xiInilFSKHJB5VtrYSS5qCnq2td98"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# دالة الترحيب التفاعلية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"يا هلا بك يا {user_name}! 😍\n\n"
        "أنا بوتك الذكي، أقدر أساعدك في:\n"
        "1️⃣ تحميل الفيديوهات (يوتيوب، فيسبوك، تيك توك، إنستا).\n"
        "2️⃣ تحويل أي نص ترسل لي إلى صوت احترافي.\n\n"
        "فقط أرسل الرابط للتحميل، أو أرسل نصاً لأحوله لصوت! 👇"
    )

# دالة تحويل النص إلى صوت
async def text_to_speech(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # إذا كان النص رابطاً، نتركه لدالة التحميل
    if text.startswith(('http://', 'https://')):
        return await download_video(update, context)

    status_msg = await update.message.reply_text("جاري تحويل النص إلى صوت... 🎙")
    voice = "ar-SA-ZariyahNeural" # صوت عربي نسائي طبيعي، يمكنك تغييره لـ ar-SA-HamedNeural لصوت رجالي
    output_file = "speech.mp3"

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        
        with open(output_file, 'rb') as audio:
            await update.message.reply_voice(voice=audio, caption="تفضل، هذا هو الملف الصوتي 🎧")
        
        os.remove(output_file)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"عذراً، فشلت في تحويل النص: {str(e)}")

# دالة التحميل (تدعم فيسبوك وغيره)
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    status_msg = await update.message.reply_text("وصلني الرابط! جاري الفحص والتحميل... 🚀")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'video.%(ext)s',
        'quiet': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
        await status_msg.edit_text("تحميل ناجح! جاري إرسال الفيديو لك الآن... 📤")
        with open(filename, 'rb') as video:
            await update.message.reply_video(video=video, caption=f"تم بحمد الله ✅\nالعنوان: {info.get('title', 'فيديو بدون عنوان')}")
        
        os.remove(filename)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"خطأ في التحميل (تأكد من أن الفيديو عام وليس خاص): {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_to_speech))
    app.run_polling()
