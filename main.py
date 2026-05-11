from telegram.ext import Application, CommandHandler, MessageHandler, filters
import config
from bot_handlers import start, addpost, availablepost, delpost, handle_video, handle_bot_reply

def main():
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addpost", addpost))
    app.add_handler(CommandHandler("availablepost", availablepost))
    app.add_handler(CommandHandler("delpost", delpost))
    
    # Catch videos/documents sent by you
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video))
    
    # Catch messages from the file sharing bot
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_bot_reply))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
