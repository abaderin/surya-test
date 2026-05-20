import json
from uuid import UUID

from redis.asyncio import Redis


class EventBus:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def channel(file_id: UUID) -> str:
        return f"file:{file_id}"

    async def publish(self, file_id: UUID, event_type: str, payload: dict) -> None:
        data = {"type": event_type, "payload": payload}
        await self._redis.publish(self.channel(file_id), json.dumps(data, default=str))
