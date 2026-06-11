from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    aws_region: str
    s3_bucket: str
    s3_upload_prefix: str
    transcribe_language_code: str
    github_repository_url: str
    github_token: str
    github_base_branch: str
    git_cache_dir: str
    kiro_api_key: str
    kiro_trust_tools: str
    progress_update_interval_seconds: int
    redis_url: str
    redis_queue_name: str
    queue_worker_concurrency: int
    transcribe_poll_interval_seconds: int
    transcribe_timeout_seconds: int
    kiro_timeout_seconds: int
    log_level: str = "INFO"


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required. Copy .env.example to .env and set it.")
    return value


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        telegram_bot_token=_required_env("TELEGRAM_BOT_TOKEN"),
        aws_region=_required_env("AWS_REGION"),
        s3_bucket=_required_env("AWS_TRANSCRIBE_BUCKET"),
        s3_upload_prefix=os.getenv("AWS_TRANSCRIBE_UPLOAD_PREFIX", "telegram-voice-notes").strip()
        or "telegram-voice-notes",
        transcribe_language_code=os.getenv("AWS_TRANSCRIBE_LANGUAGE_CODE", "en-US").strip()
        or "en-US",
        github_repository_url=_required_env("GITHUB_REPOSITORY_URL"),
        github_token=_required_env("GITHUB_TOKEN"),
        github_base_branch=os.getenv("GITHUB_BASE_BRANCH", "main").strip() or "main",
        git_cache_dir=os.getenv("GIT_CACHE_DIR", "").strip() or ".kirolets/git-cache",
        kiro_api_key=_required_env("KIRO_API_KEY"),
        kiro_trust_tools=os.getenv("KIRO_TRUST_TOOLS", "read,grep,write,bash").strip()
        or "read,grep,write,bash",
        progress_update_interval_seconds=_int_env("PROGRESS_UPDATE_INTERVAL_SECONDS", 30),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
        or "redis://localhost:6379/0",
        redis_queue_name=os.getenv("REDIS_QUEUE_NAME", "kirolets:jobs").strip() or "kirolets:jobs",
        queue_worker_concurrency=_int_env("QUEUE_WORKER_CONCURRENCY", 1),
        transcribe_poll_interval_seconds=_int_env("TRANSCRIBE_POLL_INTERVAL_SECONDS", 5),
        transcribe_timeout_seconds=_int_env("TRANSCRIBE_TIMEOUT_SECONDS", 900),
        kiro_timeout_seconds=_int_env("KIRO_TIMEOUT_SECONDS", 1800),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
