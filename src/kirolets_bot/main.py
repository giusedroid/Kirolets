import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from kirolets_bot.config import load_settings
from kirolets_bot.handlers import help_command, process_message, start
from kirolets_bot.job_queue import RedisJobQueue


async def start_queue(application: Application) -> None:
    settings = application.bot_data["settings"]
    application.bot_data["job_queue"] = RedisJobQueue(settings)


async def stop_queue(application: Application) -> None:
    queue: RedisJobQueue | None = application.bot_data.get("job_queue")
    if queue is not None:
        await queue.close()


def build_application() -> Application:
    settings = load_settings()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=settings.log_level,
    )

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(start_queue)
        .post_shutdown(stop_queue)
        .build()
    )
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE, process_message))
    return application


def main() -> None:
    application = build_application()
    application.run_polling(allowed_updates=["message"])
