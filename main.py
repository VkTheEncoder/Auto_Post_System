import os
import time
import threading
from flask import Flask

os.environ['TZ'] = 'UTC'
if hasattr(time, 'tzset'):
    time.tzset()

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import config
from bot_handlers import (
    start,
    addpost,
    availablepost,
    delpost,
    handle_video,
    handle_bot_reply,
    restart_bot,
    status_command,
    authorization_gate,
    clearqueue_command,
    myid_command,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


async def error_handler(update: object, context):
    logger.exception("Bot error occurred:", exc_info=context.error)

web_app = Flask(__name__)

@web_app.route("/")
def health_check():
    return "Auto Post Bot is running", 200


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, authorization_gate), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(CommandHandler("restart", restart_bot))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("clearqueue", clearqueue_command))

    app.add_handler(CommandHandler("availablepost", availablepost))
    app.add_handler(CommandHandler("delpost", delpost))

    app.add_handler(
        MessageHandler(
            filters.Regex(r'^/addpost') | filters.CaptionRegex(r'^/addpost'),
            addpost
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.VIDEO | filters.Document.ALL),
            handle_video
        )
    )

    app.add_handler(
          MessageHandler(
            filters.TEXT | filters.CaptionRegex(r'.+'),
            handle_bot_reply
        )
    )
    app.add_error_handler(error_handler)

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)



if __name__ == "__main__":
    main()
