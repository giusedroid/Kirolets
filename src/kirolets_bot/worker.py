import asyncio
import logging
from collections.abc import Awaitable, Callable

from telegram import Bot

from kirolets_bot.config import Settings, load_settings
from kirolets_bot.github_workflow import GitHubWorkflow, GitHubWorkflowError
from kirolets_bot.job_queue import QueuedJob, RedisJobQueue
from kirolets_bot.progress import progress_updates
from kirolets_bot.transcribe import (
    TranscriptionFailedError,
    TranscriptionTimedOutError,
    VoiceTranscriber,
)

logger = logging.getLogger(__name__)

SendMessage = Callable[[str], Awaitable[None]]


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=settings.log_level,
    )
    asyncio.run(run_workers(settings))


async def run_workers(settings: Settings) -> None:
    queue = RedisJobQueue(settings)
    bot = Bot(settings.telegram_bot_token)
    tasks: list[asyncio.Task] = []
    try:
        async with bot:
            tasks = [
                asyncio.create_task(_worker_loop(bot, settings, queue, worker_id))
                for worker_id in range(settings.queue_worker_concurrency)
            ]
            await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        await queue.close()


async def _worker_loop(bot: Bot, settings: Settings, queue: RedisJobQueue, worker_id: int) -> None:
    logger.info("Starting queue worker %s", worker_id)
    while True:
        job = await queue.dequeue()
        if job is None:
            continue

        try:
            await process_job(bot, settings, job)
        except Exception:
            logger.exception("Unhandled error while processing queued job %s", job.id)
            await bot.send_message(
                chat_id=job.chat_id,
                text="I hit an unexpected error while processing this request.",
            )


async def process_job(bot: Bot, settings: Settings, job: QueuedJob) -> None:
    async def send_message(message: str) -> None:
        await bot.send_message(chat_id=job.chat_id, text=message)

    try:
        request_text = await _job_to_request_text(bot, job, settings, send_message)
        if not request_text:
            await send_message("Send me a text message or a voice note with the task for Kiro.")
            return

        await send_message("I have the request. Checking out the repository and running Kiro now.")
        workflow = GitHubWorkflow(settings)
        async with progress_updates(
            send_message,
            "Kiro is still working on the repository. I will send the PR when it is ready.",
            settings.progress_update_interval_seconds,
        ):
            result = await workflow.execute_request(request_text, job.user_label)

        if result.changed and result.pushed_to_base:
            await send_message(
                f"Done. YOLO mode is enabled, so I pushed the changes directly to "
                f"`{settings.github_base_branch}`."
            )
        elif result.changed and result.pr_url:
            await send_message(f"Done. I opened a PR for review: {result.pr_url}")
        else:
            await send_message("Kiro completed, but there were no file changes to open as a PR.")
    except (GitHubWorkflowError, TranscriptionFailedError, TranscriptionTimedOutError) as exc:
        await send_message(f"I could not complete the request: {exc}")


async def _job_to_request_text(
    bot: Bot,
    job: QueuedJob,
    settings: Settings,
    send_message: SendMessage,
) -> str:
    if job.kind == "text":
        return (job.text or "").strip()

    if job.kind != "voice" or job.voice_file_id is None:
        return ""

    await send_message("Received the voice note. Downloading it now.")
    telegram_file = await bot.get_file(job.voice_file_id)
    audio_bytes = bytes(await telegram_file.download_as_bytearray())

    await send_message("Uploading the voice note to S3 and starting transcription.")
    transcriber = VoiceTranscriber(settings)
    async with progress_updates(
        send_message,
        "Still waiting for Amazon Transcribe to finish the voice note.",
        settings.progress_update_interval_seconds,
    ):
        result = await transcriber.transcribe_voice_note(audio_bytes)

    await send_message("Transcription complete. Passing the transcript to Kiro.")
    return result.text
