from telegram import Update
from telegram.ext import ContextTypes

from kirolets_bot.config import Settings
from kirolets_bot.job_queue import RedisJobQueue


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if not await _authorize(update, context):
        return

    await update.message.reply_text("Kirolets bot is online.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if not await _authorize(update, context):
        return

    await update.message.reply_text("Available commands: /start, /help")


async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if not await _authorize(update, context):
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


async def _authorize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    settings: Settings = context.application.bot_data["settings"]
    allowed_user_ids = settings.telegram_allowed_user_ids
    if not allowed_user_ids:
        return True

    user_id = update.effective_user.id if update.effective_user is not None else None
    if user_id in allowed_user_ids:
        return True

    if update.message is not None:
        await update.message.reply_text("You are not allowed to use this bot.")

    return False
