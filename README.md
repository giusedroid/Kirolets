# Kirolets Telegram Bot

Kirolets lets Kiro users ask for code changes from Telegram.

The long-term idea is simple: give Kiro users a lightweight interface they can use from
wherever they already are. Telegram is the first surface. Later, the same request workflow
can be exposed from other chat apps, webhooks, internal tools, or automation entrypoints.

Kiro itself provides an agentic development experience across IDE, CLI, and web. Kirolets
focuses on the CLI path: it turns a Telegram text message or voice note into a headless
Kiro CLI run against a configured GitHub repository, then returns a pull request for review.

## How It Uses Kiro

Kiro's headless CLI mode is designed for automation contexts such as CI/CD pipelines,
code review, test generation, and build troubleshooting. In that mode, Kiro runs without
an interactive terminal by receiving a prompt up front:

```bash
kiro-cli chat --no-interactive "your prompt here"
```

Because there is no human sitting inside the terminal to approve tool calls, Kirolets uses
scoped tool trust through `--trust-tools`:

```bash
kiro-cli chat --no-interactive --trust-tools=read,grep,write,bash "implement the request"
```

The Kiro API key is supplied through `KIRO_API_KEY`, matching the headless CLI
authentication model. Keep that value in deployment secrets and never commit it.

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
2. Uses text messages directly when no transcription is needed.
3. Updates a local bare Git cache for the configured GitHub repository.
4. Creates a temporary worktree and branch for the Telegram request.
5. Runs Kiro CLI in headless mode with the message or transcript as the prompt.
6. Commits any generated changes.
7. Invokes Kiro again with the original request, commit log, and diff stat to draft the PR title and description.
8. Pushes the branch, opens a GitHub PR, and sends the PR link back to Telegram.

Long-running transcription and Kiro stages send progress updates back to the chat.

## Required Configuration

All runtime configuration is provided through environment variables:

```env
TELEGRAM_BOT_TOKEN=

AWS_REGION=
AWS_TRANSCRIBE_BUCKET=
AWS_TRANSCRIBE_UPLOAD_PREFIX=telegram-voice-notes
AWS_TRANSCRIBE_LANGUAGE_CODE=en-US

GITHUB_REPOSITORY_URL=
GITHUB_TOKEN=
GITHUB_BASE_BRANCH=main
GIT_CACHE_DIR=.kirolets/git-cache

KIRO_API_KEY=
KIRO_TRUST_TOOLS=read,grep,write,bash

PROGRESS_UPDATE_INTERVAL_SECONDS=30
TRANSCRIBE_POLL_INTERVAL_SECONDS=5
TRANSCRIBE_TIMEOUT_SECONDS=900
KIRO_TIMEOUT_SECONDS=1800
```

Use narrowly scoped `KIRO_TRUST_TOOLS` values where possible. Kiro's docs recommend
specific tool categories over trusting every tool, which matches the bot's default.

## Git Workspace Strategy

Kirolets keeps a bare Git repository cache under `GIT_CACHE_DIR` instead of cloning the
whole repository from GitHub for every request. Each Telegram request fetches the latest
refs into that cache, creates a temporary linked worktree, lets Kiro edit files there,
then removes the worktree after pushing the PR branch.

This keeps each request isolated while avoiding repeated full repository downloads.

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
