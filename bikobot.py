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

# 1. دالة الترحيب (start)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"يا هلا بك يا {user_name}! 😍\n\n"
        "أنا بوتك الذكي، أرسل لي أي رابط فيديو للتحميل، أو أي نص لأحوله لك لصوت بشري احترافي. 🎙\n\n"
        "للمساعدة اضغط على /help"
    )

# 2. دالة المساعدة (help) - لحل مشكلة القائمة
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **طريقة استخدام البوت:**\n\n"
        "📥 **للتحميل:** فقط أرسل رابط الفيديو (يوتيوب، فيسبوك، تيك توك، إنستجرام) وسأقوم بإرساله لك.\n\n"
        "🗣 **لتحويل نص لصوت:** أرسل أي جملة نصية (ليست رابطاً) وسأحولها لك لملف صوتي عالي الجودة.\n\n"
        "✅ البوت يعمل تلقائياً وبسرعة عالية."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# 3. دالة معالجة النصوص (تفرق بين الرابط والنص العادي)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # إذا كان النص يبدأ بـ http فهو رابط تحميل
    if text.startswith(('http://', 'https://')):
        return await download_video(update, context)
    
    # إذا كان نصاً عادياً، نقوم بتحويله لصوت
    return await text_to_speech(update, context)

# 4. دالة تحويل النص إلى صوت
async def text_to_speech(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    status_msg = await update.message.reply_text("جاري تحويل نصك إلى صوت رائع... 🎙")
    
    # إعدادات الصوت (صوت عربي سعودي طبيعي)
    voice = "ar-SA-ZariyahNeural"
    output_file = f"voice_{update.effective_user.id}.mp3"

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        
        with open(output_file, 'rb') as audio:
            await update.message.reply_voice(voice=audio, caption="تفضل، نصك مسموعاً 🎧")
        
        os.remove(output_file)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"عذراً، حدث خطأ في معالجة الصوت: {str(e)}")

# 5. دالة التحميل الشاملة (فيسبوك وغيره)
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    status_msg = await update.message.reply_text("وصلني الرابط! جاري التحميل... 🚀")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': f'video_{update.effective_user.id}.%(ext)s',
        'quiet': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
        await status_msg.edit_text("جاري إرسال الفيديو... 📤")
        with open(filename, 'rb') as video:
            await update.message.reply_video(video=video, caption=f"تم التحميل ✅\n{info.get('title', '')}")
        
        os.remove(filename)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"خطأ في التحميل: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    # تسجيل الأوامر
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    
    # تسجيل معالج الرسائل العام (نص أو روابط)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    app.run_polling()
