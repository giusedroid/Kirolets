import logging

from telegram.ext import Application, CommandHandler

from kirolets_bot.config import load_settings
from kirolets_bot.handlers import help_command, start


def build_application() -> Application:
    settings = load_settings()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=settings.log_level,
    )

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    return application


def main() -> None:
    application = build_application()
    application.run_polling(allowed_updates=["message"])
