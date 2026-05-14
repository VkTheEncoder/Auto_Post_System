import os
import time
# 100% FOOLPROOF TIMEZONE FIX: Force system to UTC before Telegram even loads
os.environ['TZ'] = 'UTC'
if hasattr(time, 'tzset'):
    time.tzset()

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import config
from bot_handlers import start, addpost, availablepost, delpost, handle_video, handle_bot_reply

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    app = Application.builder().token(config.BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("availablepost", availablepost))
    app.add_handler(CommandHandler("delpost", delpost))
    
    app.add_handler(MessageHandler(filters.Regex(r'^/addpost') | filters.CaptionRegex(r'^/addpost'), addpost))
    
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_bot_reply))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
