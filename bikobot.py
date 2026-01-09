import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ضع التوكن الخاص بك هنا مباشرة بين علامتي التنصيص
TOKEN = "8304502500:AAHA11xiInilFSKHJB5VtrYSS5qCnq2td98"

# إعداد السجلات لمراقبة أداء البوت
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# دالة الترحيب بالاسم
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name  # جلب اسم المستخدم
    welcome_text = (
        f"أهلاً بك يا {user_name} في بوت التحميل الذكي! 🌟\n\n"
        "أنا هنا لمساعدتك في تحميل الفيديوهات والمقاطع الصوتية.\n"
        "فقط أرسل لي رابط الفيديو وسأبدأ بالعمل فوراً. 🚀"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_text)

# دالة التعامل مع الرسائل (هنا يمكنك إضافة منطق التحميل الخاص بك)
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="جاري استلام الرابط ومعالجته... ⏳")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    # تعريف الأوامر
    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)
    
    application.add_handler(start_handler)
    application.add_handler(echo_handler)
    
    # تشغيل البوت
    application.run_polling()
