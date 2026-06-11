import asyncio
import logging
from collections.abc import Awaitable, Callable

from telegram.ext import Application

from kirolets_bot.config import Settings
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


async def start_workers(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    queue = RedisJobQueue(settings)
    application.bot_data["job_queue"] = queue
    application.bot_data["worker_tasks"] = [
        asyncio.create_task(_worker_loop(application, queue, worker_id))
        for worker_id in range(settings.queue_worker_concurrency)
    ]


async def stop_workers(application: Application) -> None:
    tasks: list[asyncio.Task] = application.bot_data.get("worker_tasks", [])
    for task in tasks:
        task.cancel()

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    queue: RedisJobQueue | None = application.bot_data.get("job_queue")
    if queue is not None:
        await queue.close()


async def _worker_loop(application: Application, queue: RedisJobQueue, worker_id: int) -> None:
    logger.info("Starting queue worker %s", worker_id)
    while True:
        job = await queue.dequeue()
        if job is None:
            continue

        try:
            await process_job(application, job)
        except Exception:
            logger.exception("Unhandled error while processing queued job %s", job.id)
            await application.bot.send_message(
                chat_id=job.chat_id,
                text="I hit an unexpected error while processing this request.",
            )


async def process_job(application: Application, job: QueuedJob) -> None:
    settings: Settings = application.bot_data["settings"]

    async def send_message(message: str) -> None:
        await application.bot.send_message(chat_id=job.chat_id, text=message)

    try:
        request_text = await _job_to_request_text(application, job, settings, send_message)
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

        if result.changed and result.pr_url:
            await send_message(f"Done. I opened a PR for review: {result.pr_url}")
        else:
            await send_message("Kiro completed, but there were no file changes to open as a PR.")
    except (GitHubWorkflowError, TranscriptionFailedError, TranscriptionTimedOutError) as exc:
        await send_message(f"I could not complete the request: {exc}")


async def _job_to_request_text(
    application: Application,
    job: QueuedJob,
    settings: Settings,
    send_message: SendMessage,
) -> str:
    if job.kind == "text":
        return (job.text or "").strip()

    if job.kind != "voice" or job.voice_file_id is None:
        return ""

    await send_message("Received the voice note. Downloading it now.")
    telegram_file = await application.bot.get_file(job.voice_file_id)
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
