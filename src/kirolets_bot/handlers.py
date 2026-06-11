from telegram import Update
from telegram.ext import ContextTypes

from kirolets_bot.job_queue import RedisJobQueue


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


async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    queue: RedisJobQueue = context.application.bot_data["job_queue"]
    chat_id = update.message.chat_id
    user_label = _user_label(update)

    if update.message.voice is not None:
        job = await queue.enqueue_voice(chat_id, user_label, update.message.voice.file_id)
        queue_size = await queue.size()
        await update.message.reply_text(f"Queued voice request {job.id}. Position in queue: {queue_size}.")
        return

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Send me a text message or a voice note with the task for Kiro.")
        return

    job = await queue.enqueue_text(chat_id, user_label, text)
    queue_size = await queue.size()
    await update.message.reply_text(f"Queued request {job.id}. Position in queue: {queue_size}.")


def _user_label(update: Update) -> str:
    if update.effective_user is None:
        return "unknown"

    if update.effective_user.username:
        return update.effective_user.username

    return str(update.effective_user.id)
