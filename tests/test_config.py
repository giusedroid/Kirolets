import pytest

from kirolets_bot.config import Settings, load_settings


def test_load_settings_reads_required_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-123")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_TRANSCRIBE_BUCKET", "bucket")
    monkeypatch.setenv("GITHUB_REPOSITORY_URL", "https://github.com/example/repo.git")
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")
    monkeypatch.setenv("KIRO_API_KEY", "kiro-token")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    assert load_settings() == Settings(
        telegram_bot_token="token-123",
        aws_region="eu-west-1",
        s3_bucket="bucket",
        s3_upload_prefix="telegram-voice-notes",
        transcribe_language_code="en-US",
        github_repository_url="https://github.com/example/repo.git",
        github_token="github-token",
        github_base_branch="main",
        git_cache_dir=".kirolets/git-cache",
        kiro_api_key="kiro-token",
        kiro_trust_tools="read,grep,write,bash",
        progress_update_interval_seconds=30,
        redis_url="redis://localhost:6379/0",
        redis_queue_name="kirolets:jobs",
        queue_worker_concurrency=1,
        yolo=False,
        transcribe_poll_interval_seconds=5,
        transcribe_timeout_seconds=900,
        kiro_timeout_seconds=1800,
        log_level="DEBUG",
    )


def test_load_settings_requires_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN is required"):
        load_settings()
