from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import uuid

from redis.asyncio import Redis

from kirolets_bot.config import Settings


@dataclass(frozen=True)
class QueuedJob:
    id: str
    chat_id: int
    user_label: str
    kind: str
    text: str | None = None
    voice_file_id: str | None = None


class RedisJobQueue:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)

    async def enqueue_text(self, chat_id: int, user_label: str, text: str) -> QueuedJob:
        job = QueuedJob(
            id=uuid.uuid4().hex,
            chat_id=chat_id,
            user_label=user_label,
            kind="text",
            text=text,
        )
        await self.enqueue(job)
        return job

    async def enqueue_voice(self, chat_id: int, user_label: str, voice_file_id: str) -> QueuedJob:
        job = QueuedJob(
            id=uuid.uuid4().hex,
            chat_id=chat_id,
            user_label=user_label,
            kind="voice",
            voice_file_id=voice_file_id,
        )
        await self.enqueue(job)
        return job

    async def enqueue(self, job: QueuedJob) -> None:
        await self._redis.rpush(self._settings.redis_queue_name, serialize_job(job))

    async def dequeue(self, timeout_seconds: int = 5) -> QueuedJob | None:
        result = await self._redis.blpop(self._settings.redis_queue_name, timeout=timeout_seconds)
        if result is None:
            return None

        _, payload = result
        return deserialize_job(payload)

    async def size(self) -> int:
        return await self._redis.llen(self._settings.redis_queue_name)

    async def close(self) -> None:
        await self._redis.aclose()


def serialize_job(job: QueuedJob) -> str:
    return json.dumps(asdict(job), separators=(",", ":"))


def deserialize_job(payload: str) -> QueuedJob:
    data = json.loads(payload)
    return QueuedJob(
        id=data["id"],
        chat_id=int(data["chat_id"]),
        user_label=data["user_label"],
        kind=data["kind"],
        text=data.get("text"),
        voice_file_id=data.get("voice_file_id"),
    )
