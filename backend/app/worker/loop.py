import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_event_bus, get_processor, get_storage
from app.core.settings import settings
from app.db.session import SessionLocal
from app.services.task_service import TaskService


class WorkerLoop:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def run(self) -> None:
        while not self._stop.is_set():
            async with SessionLocal() as session:
                await self._run_once(session)
            await asyncio.sleep(settings.worker_poll_seconds)

    async def _run_once(self, session: AsyncSession) -> None:
        service = TaskService(session, get_storage(), get_processor(), await get_event_bus())
        next_task = await service.claim_next_task(settings.worker_stale_after_seconds)
        if next_task:
            await service.execute_task(next_task)
