from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.api.deps import get_event_bus, get_processor, get_storage
from app.db.session import get_session
from app.services.task_service import TaskService


@asynccontextmanager
async def task_service_context() -> AsyncIterator[TaskService]:
    async for session in get_session():
        yield TaskService(session, get_storage(), get_processor(), await get_event_bus())
