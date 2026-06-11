from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    log_level: str = "INFO"


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required. Copy .env.example to .env and set it.")

    return Settings(
        telegram_bot_token=token,
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
