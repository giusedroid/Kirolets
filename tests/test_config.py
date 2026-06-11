import pytest

from kirolets_bot.config import Settings, load_settings


def test_load_settings_reads_required_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-123")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    assert load_settings() == Settings(telegram_bot_token="token-123", log_level="DEBUG")


def test_load_settings_requires_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN is required"):
        load_settings()
