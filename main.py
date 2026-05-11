import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import config
from bot_handlers import start, addpost, availablepost, delpost, handle_video, handle_bot_reply

# Enable logging to see errors in the terminal
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpost", addpost))
    app.add_handler(CommandHandler("availablepost", availablepost))
    app.add_handler(CommandHandler("delpost", delpost))
    
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_bot_reply))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
