from collections.abc import AsyncIterator

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.session import get_session
from app.services.events import EventBus
from app.services.processor import ProcessorService
from app.services.storage import StorageService
from app.services.surya import SuryaPredictors
from app.services.task_service import TaskService

_storage = StorageService()
_predictors = SuryaPredictors(settings.storage_root_path / ".gpu-predictor.lock")
_processor = ProcessorService(_predictors)
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


async def get_task_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    return TaskService(db, get_storage(), get_processor(), await get_event_bus())
