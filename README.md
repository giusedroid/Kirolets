# Kirolets Telegram Bot

A Telegram bot workspace for Kirolets.

## Requirements

- uv
- Python 3.14
- A Telegram bot token from BotFather

## Setup

```powershell
uv python install 3.14
uv sync --dev
Copy-Item .env.example .env
```

Edit `.env` and set `TELEGRAM_BOT_TOKEN`.
Also configure the AWS, GitHub, and Kiro variables shown in `.env.example`.

## Bot Flow

For each text message or voice note, the bot:

1. Transcribes voice notes through S3 and Amazon Transcribe with speaker diarization enabled for up to 10 speakers.
2. Uses text messages directly.
3. Clones the configured GitHub repository into a temporary workspace.
4. Creates a new branch for the Telegram request.
5. Runs Kiro CLI in headless mode with the message or transcript as the prompt.
6. Commits any generated changes, pushes the branch, opens a GitHub PR, and sends the PR link back to Telegram.

Long-running transcription and Kiro stages send progress updates back to the chat.

## Run

```powershell
uv run kirolets-bot
```

During development you can also run:

```powershell
uv run python -m kirolets_bot
```

## Test

```powershell
uv run pytest
```

## Deployment Requirements

`requirements.txt` is exported from `uv.lock` for platforms that expect pip-style
dependency files:

```powershell
uv export --format requirements-txt --no-dev --no-hashes --output-file requirements.txt
```

## Docker

```powershell
docker build -t kirolets-bot .
docker run --env-file .env kirolets-bot
```

The Docker image includes `git` and installs `kiro-cli` using Kiro's documented installer:

```bash
curl -fsSL https://cli.kiro.dev/install | bash
```

## Project Layout

```text
src/kirolets_bot/     Bot application code
tests/                Automated tests
.env.example          Example local environment file
```
