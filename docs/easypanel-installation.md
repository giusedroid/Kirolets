# EasyPanel Installation Guide

This guide deploys Kirolets as three EasyPanel services:

- `kirolets-redis`: Redis queue.
- `kirolets-bot`: Telegram intake service.
- `kirolets-worker`: background execution service.

Kirolets is one codebase and one Docker image. The bot and worker behave differently
because they start different commands from the same image:

```text
kirolets-bot     -> receives Telegram updates and enqueues jobs
kirolets-worker  -> consumes Redis jobs and runs AWS/Kiro/GitHub work
```

Redis is the boundary between the two process roles:

```text
Telegram -> kirolets-bot -> Redis -> kirolets-worker -> AWS/Kiro/GitHub -> Telegram
```

## Why Three Services

The split keeps Telegram intake responsive while Kiro is doing long-running work.

- The bot service should stay lightweight and only enqueue jobs.
- The worker service can take minutes to transcribe audio, run Kiro, push code, and open PRs.
- Redis gives the system a durable handoff point between intake and execution.

This is still a modular monolith. There are not three separate applications or repos.
EasyPanel simply runs the same Docker image with different commands.

## Prerequisites

You need:

- An EasyPanel server with a project created.
- Access to the GitHub repository that contains Kirolets.
- A Telegram bot token from BotFather.
- AWS credentials that can use S3 and Amazon Transcribe.
- An S3 bucket for voice-note uploads.
- A GitHub token that can clone, push branches, and create PRs in the target repository.
- A Kiro API key for headless Kiro CLI usage.

EasyPanel references used while preparing this guide:

- App Service docs: https://easypanel.io/docs/services/app
- Redis Service docs: https://easypanel.io/docs/services/redis
- Compose Service docs: https://easypanel.io/docs/services/compose

The recommended EasyPanel setup is two App Services plus one Redis Service. EasyPanel has
a Compose Service page, but the official docs currently say that Compose documentation is
coming soon, so the first-class service setup is easier to teach and operate.

## Required Environment Variables

Use the same values for `kirolets-bot` and `kirolets-worker` unless noted otherwise.

### Telegram

```env
TELEGRAM_BOT_TOKEN=
```

The token from BotFather. Both services need this:

- The bot receives updates.
- The worker sends progress and final result messages back to Telegram.

### AWS

```env
AWS_REGION=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_TRANSCRIBE_BUCKET=
AWS_TRANSCRIBE_UPLOAD_PREFIX=telegram-voice-notes
AWS_TRANSCRIBE_LANGUAGE_CODE=en-US
```

The worker uses these to upload voice notes to S3 and start Amazon Transcribe jobs.
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are read by `boto3` automatically.

Minimum AWS permissions for the worker:

- `s3:PutObject` on the upload prefix.
- `transcribe:StartTranscriptionJob`.
- `transcribe:GetTranscriptionJob`.

### GitHub

```env
GITHUB_REPOSITORY_URL=
GITHUB_TOKEN=
GITHUB_USERNAME=
GITHUB_EMAIL=
GITHUB_BASE_BRANCH=main
GIT_CACHE_DIR=.kirolets/git-cache
```

`GITHUB_REPOSITORY_URL` should be the target repository Kiro edits, for example:

```env
GITHUB_REPOSITORY_URL=https://github.com/giusedroid/Kirolets.git
```

Token requirements:

- Clone/fetch repository contents.
- Push request branches.
- Create pull requests.
- If `YOLO=true`, push directly to `GITHUB_BASE_BRANCH`.

For a GitHub fine-grained personal access token, start with:

- Contents: read/write.
- Pull requests: read/write.
- Metadata: read.

Branch protection can still block `YOLO=true` pushes, even when the token has write access.

`GITHUB_USERNAME` and `GITHUB_EMAIL` are configured as `git config user.name` and
`git config user.email` inside each temporary worktree before committing. Without them,
containerized commits can fail with Git's author identity error.

### Kiro

```env
KIRO_API_KEY=
KIRO_TRUST_TOOLS=read,grep,write,bash
```

`KIRO_API_KEY` is used by the Kiro CLI in headless mode. `KIRO_TRUST_TOOLS` controls which
Kiro tools can run without interactive approval. Keep this scoped as narrowly as the target
workflow allows.

### Redis And Workers

```env
REDIS_URL=
REDIS_QUEUE_NAME=kirolets:jobs
QUEUE_WORKER_CONCURRENCY=1
```

Set `REDIS_URL` from the EasyPanel Redis service connection details. The hostname depends
on your EasyPanel project and service naming. A typical internal value looks like:

```env
REDIS_URL=redis://kirolets-redis:6379/0
```

Keep `QUEUE_WORKER_CONCURRENCY=1` while the product is young. It ensures Kiro jobs run one
at a time.

### Runtime Behavior

```env
PROGRESS_UPDATE_INTERVAL_SECONDS=30
TRANSCRIBE_POLL_INTERVAL_SECONDS=5
TRANSCRIBE_TIMEOUT_SECONDS=900
KIRO_TIMEOUT_SECONDS=1800
YOLO=false
LOG_LEVEL=INFO
```

`YOLO=false` is the safe default: Kirolets opens a PR.

`YOLO=true` skips PR creation and pushes directly to `GITHUB_BASE_BRANCH`. Treat this as a
deliberate productivity-as-code shortcut for trusted repositories.

## Step 1: Create The Redis Service

1. In EasyPanel, open your project.
2. Add a new Redis Service.
3. Name it `kirolets-redis`.
4. Deploy it.
5. Open the service credentials or connection details.
6. Copy the internal Redis connection URL or host/port.

Redis does not need to be public. Kirolets only needs internal service-to-service access.
Expose Redis publicly only if you have a specific operational reason.

## Step 2: Create The Bot App Service

1. Add a new App Service.
2. Name it `kirolets-bot`.
3. Select your GitHub repository as the source.
4. Use the branch you want to deploy, usually `main`.
5. Let EasyPanel build from the repository `Dockerfile`.
6. Set the service command to:

```bash
kirolets-bot
```

7. Add environment variables:

```env
TELEGRAM_BOT_TOKEN=
REDIS_URL=
REDIS_QUEUE_NAME=kirolets:jobs
LOG_LEVEL=INFO
```

The bot service does not need AWS, GitHub, or Kiro secrets because it only receives Telegram
messages and enqueues jobs.

8. Deploy the service.
9. Open logs and confirm the process starts without crashing.

The bot does not expose an HTTP port in the current polling setup, so you do not need a
public domain for it yet.

## Step 3: Create The Worker App Service

1. Add another App Service.
2. Name it `kirolets-worker`.
3. Use the same GitHub repository and branch as the bot service.
4. Let EasyPanel build from the same `Dockerfile`.
5. Set the service command to:

```bash
kirolets-worker
```

6. Add the full worker environment:

```env
TELEGRAM_BOT_TOKEN=

AWS_REGION=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_TRANSCRIBE_BUCKET=
AWS_TRANSCRIBE_UPLOAD_PREFIX=telegram-voice-notes
AWS_TRANSCRIBE_LANGUAGE_CODE=en-US

GITHUB_REPOSITORY_URL=
GITHUB_TOKEN=
GITHUB_USERNAME=
GITHUB_EMAIL=
GITHUB_BASE_BRANCH=main
GIT_CACHE_DIR=.kirolets/git-cache

KIRO_API_KEY=
KIRO_TRUST_TOOLS=read,grep,write,bash

REDIS_URL=
REDIS_QUEUE_NAME=kirolets:jobs
QUEUE_WORKER_CONCURRENCY=1

PROGRESS_UPDATE_INTERVAL_SECONDS=30
TRANSCRIBE_POLL_INTERVAL_SECONDS=5
TRANSCRIBE_TIMEOUT_SECONDS=900
KIRO_TIMEOUT_SECONDS=1800
YOLO=false
LOG_LEVEL=INFO
```

7. Deploy the service.
8. Open logs and confirm the worker starts and waits for Redis jobs.

## Step 4: Configure Persistent Git Cache

The worker uses `GIT_CACHE_DIR` for a bare Git cache. This avoids recloning the whole target
repo for every Telegram request.

For production, add a volume mount to the worker service:

```text
Mount path: /app/.kirolets
```

Then set:

```env
GIT_CACHE_DIR=/app/.kirolets/git-cache
```

Without this mount, the cache still works, but it is recreated whenever the worker
container is replaced.

## Step 5: Verify The Deployment

Send a text message to the Telegram bot:

```text
Update the README with a short note saying Kirolets is running from EasyPanel.
```

Expected behavior:

1. Bot replies that the request was queued.
2. Worker sends progress updates.
3. Worker sends Kiro's response.
4. With `YOLO=false`, worker opens a GitHub PR and sends the PR link.
5. With `YOLO=true`, worker pushes directly to `GITHUB_BASE_BRANCH` and says so.

For a voice-note test, send a short voice message. The worker should upload it to S3, start
Amazon Transcribe, wait for the transcript, and then pass the transcript to Kiro.

## Step 6: Enable Auto Deploy

Once both App Services work:

1. Enable EasyPanel auto deploy for `kirolets-bot`.
2. Enable EasyPanel auto deploy for `kirolets-worker`.
3. Push a small docs change to GitHub.
4. Confirm both services redeploy successfully.

Because both services build from the same Dockerfile, they should stay on the same code
version.

## Production Notes

- Keep `QUEUE_WORKER_CONCURRENCY=1` until you are comfortable with parallel Kiro runs.
- Keep `YOLO=false` for repositories where review matters.
- Use `YOLO=true` only for trusted repositories and low-risk automation.
- Do not expose Redis publicly unless required.
- Prefer fine-grained GitHub tokens over broad classic tokens.
- Give AWS credentials the smallest useful permission set.
- Use EasyPanel logs as the first place to debug startup or queue-processing issues.

## Troubleshooting

### Bot receives messages but nothing happens

Check:

- `REDIS_URL` is identical in bot and worker.
- Redis service is running.
- Worker service is deployed and not crashing.
- `REDIS_QUEUE_NAME` matches in both services.

### Worker cannot download voice notes

Check:

- `TELEGRAM_BOT_TOKEN` is present in the worker service.
- The worker can reach Telegram over outbound HTTPS.

### Transcription never completes

Check:

- `AWS_REGION` matches the S3 bucket and Transcribe region you expect.
- `AWS_TRANSCRIBE_BUCKET` exists.
- AWS credentials have S3 and Transcribe permissions.
- Audio files are appearing under `AWS_TRANSCRIBE_UPLOAD_PREFIX`.

### Kiro fails immediately

Check:

- `KIRO_API_KEY` is set in the worker service.
- The Docker image installed `kiro-cli` successfully during build.
- `KIRO_TRUST_TOOLS` includes the tools required for the task.

### GitHub PR creation fails

Check:

- `GITHUB_TOKEN` has pull request write permission.
- `GITHUB_TOKEN` has contents write permission.
- `GITHUB_REPOSITORY_URL` points to the target repo.
- The base branch in `GITHUB_BASE_BRANCH` exists.

### YOLO push fails

Check:

- Branch protection does not block direct pushes.
- The token has permission to push to `GITHUB_BASE_BRANCH`.
- The remote branch has not moved in a way that requires a rebase.

## Course Framing: Productivity As Code

Kirolets is a useful teaching example because the productivity workflow is encoded as
infrastructure and application behavior:

- Telegram is the human interface.
- Redis is the work queue.
- The worker is the automation boundary.
- Kiro CLI is the coding agent.
- GitHub PRs are the review artifact.
- Environment variables define operational policy, including safe PR mode versus YOLO mode.

The core lesson: productivity tools become more powerful when they are deployed like
software systems, with queues, secrets, logs, permissions, deployment boundaries, and
reviewable outputs.
