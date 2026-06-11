from telegram import Update
from telegram.ext import ContextTypes

from kirolets_bot.config import Settings
from kirolets_bot.github_workflow import GitHubWorkflow, GitHubWorkflowError
from kirolets_bot.progress import progress_updates
from kirolets_bot.transcribe import (
    TranscriptionFailedError,
    TranscriptionTimedOutError,
    VoiceTranscriber,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context

    if update.message is None:
        return

    await update.message.reply_text("Kirolets bot is online.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context

    if update.message is None:
        return

    await update.message.reply_text("Available commands: /start, /help")


async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    send_message = update.message.reply_text

    try:
        request_text = await _message_to_request_text(update, context, settings)
        if not request_text:
            await send_message("Send me a text message or a voice note with the task for Kiro.")
            return

        await send_message("I have the request. Checking out the repository and running Kiro now.")
        workflow = GitHubWorkflow(settings)
        user_label = _user_label(update)

        async with progress_updates(
            send_message,
            "Kiro is still working on the repository. I will send the PR when it is ready.",
            settings.progress_update_interval_seconds,
        ):
            result = await workflow.execute_request(request_text, user_label)

        if result.changed and result.pr_url:
            await send_message(f"Done. I opened a PR for review: {result.pr_url}")
        else:
            await send_message("Kiro completed, but there were no file changes to open as a PR.")
    except (GitHubWorkflowError, TranscriptionFailedError, TranscriptionTimedOutError) as exc:
        await send_message(f"I could not complete the request: {exc}")


async def _message_to_request_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    settings: Settings,
) -> str:
    message = update.message
    if message is None:
        return ""

    if message.voice is not None:
        await message.reply_text("Received the voice note. Downloading it now.")
        telegram_file = await context.bot.get_file(message.voice.file_id)
        audio_bytes = bytes(await telegram_file.download_as_bytearray())

        await message.reply_text("Uploading the voice note to S3 and starting transcription.")
        transcriber = VoiceTranscriber(settings)
        async with progress_updates(
            message.reply_text,
            "Still waiting for Amazon Transcribe to finish the voice note.",
            settings.progress_update_interval_seconds,
        ):
            result = await transcriber.transcribe_voice_note(audio_bytes)

        await message.reply_text("Transcription complete. Passing the transcript to Kiro.")
        return result.text

    return (message.text or "").strip()


def _user_label(update: Update) -> str:
    if update.effective_user is None:
        return "unknown"

    if update.effective_user.username:
        return update.effective_user.username

    return str(update.effective_user.id)
