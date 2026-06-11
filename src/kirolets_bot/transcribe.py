import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import PurePosixPath
import uuid
from urllib.request import urlopen

import boto3

from kirolets_bot.config import Settings


@dataclass(frozen=True)
class TranscriptionResult:
    job_name: str
    s3_uri: str
    text: str


class TranscriptionFailedError(RuntimeError):
    pass


class TranscriptionTimedOutError(TimeoutError):
    pass


class VoiceTranscriber:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._s3 = boto3.client("s3", region_name=settings.aws_region)
        self._transcribe = boto3.client("transcribe", region_name=settings.aws_region)

    async def transcribe_voice_note(self, audio: bytes, file_extension: str = "ogg") -> TranscriptionResult:
        job_name = self._job_name()
        key = self._object_key(job_name, file_extension)
        s3_uri = f"s3://{self._settings.s3_bucket}/{key}"

        await asyncio.to_thread(
            self._s3.put_object,
            Bucket=self._settings.s3_bucket,
            Key=key,
            Body=audio,
            ContentType="audio/ogg",
        )

        await asyncio.to_thread(
            self._transcribe.start_transcription_job,
            TranscriptionJobName=job_name,
            LanguageCode=self._settings.transcribe_language_code,
            Media={"MediaFileUri": s3_uri},
            Settings={
                "ShowSpeakerLabels": True,
                "MaxSpeakerLabels": 10,
            },
        )

        text = await self._wait_for_transcript(job_name)
        return TranscriptionResult(job_name=job_name, s3_uri=s3_uri, text=text)

    async def _wait_for_transcript(self, job_name: str) -> str:
        elapsed_seconds = 0
        while elapsed_seconds <= self._settings.transcribe_timeout_seconds:
            response = await asyncio.to_thread(
                self._transcribe.get_transcription_job,
                TranscriptionJobName=job_name,
            )
            job = response["TranscriptionJob"]
            status = job["TranscriptionJobStatus"]

            if status == "COMPLETED":
                transcript_uri = job["Transcript"]["TranscriptFileUri"]
                return await asyncio.to_thread(self._fetch_transcript_text, transcript_uri)

            if status == "FAILED":
                reason = job.get("FailureReason", "Unknown failure")
                raise TranscriptionFailedError(reason)

            await asyncio.sleep(self._settings.transcribe_poll_interval_seconds)
            elapsed_seconds += self._settings.transcribe_poll_interval_seconds

        raise TranscriptionTimedOutError(f"Transcription job {job_name} timed out.")

    def _fetch_transcript_text(self, transcript_uri: str) -> str:
        with urlopen(transcript_uri, timeout=30) as response:
            transcript = json.loads(response.read().decode("utf-8"))

        return transcript["results"]["transcripts"][0]["transcript"].strip()

    def _object_key(self, job_name: str, file_extension: str) -> str:
        extension = file_extension.strip(".") or "ogg"
        return str(PurePosixPath(self._settings.s3_upload_prefix) / f"{job_name}.{extension}")

    def _job_name(self) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        return f"kirolets-{timestamp}-{uuid.uuid4().hex[:8]}"
