from collections.abc import AsyncIterator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.session import get_session
from app.services.events import EventBus
from app.services.processor import ProcessorService
from app.services.storage import StorageService

_storage = StorageService()
_processor = ProcessorService()
_redis: Redis | None = None


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


def get_storage() -> StorageService:
    return _storage


def get_processor() -> ProcessorService:
    return _processor


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def get_event_bus() -> EventBus:
    return EventBus(await get_redis())
