from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context

    if update.message is None:
        return

    await update.message.reply_text("Kirolets bot is online.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context

    if update.message is None:
        return

    await update.message.reply_text("Available commands: /start, /help")
