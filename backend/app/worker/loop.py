import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from app.models.enums import TaskType
from app.services.task_service import TaskService
from app.worker.deps import task_service_context

TaskServiceContextFactory = Callable[[], AbstractAsyncContextManager[TaskService]]


class WorkerLoop:
    def __init__(
        self,
        *,
        poll_seconds: float,
        stale_after_seconds: int,
        worker_task_types_set: set[TaskType] | None,
        cpu_threads: int,
        task_service_context_factory: TaskServiceContextFactory = task_service_context,
    ) -> None:
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self.poll_seconds = poll_seconds
        self.stale_after_seconds = stale_after_seconds
        self.worker_task_types_set = worker_task_types_set
        self.cpu_threads = cpu_threads
        self.task_service_context_factory = task_service_context_factory

    async def start(self) -> None:
        self._stop.clear()
        self._tasks = [asyncio.create_task(self.run()) for _ in range(self.cpu_threads)]

    async def stop(self) -> None:
        self._stop.set()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks = []

    async def run(self) -> None:
        while not self._stop.is_set():
            async with self.task_service_context_factory() as service:
                await self._run_once(service)
            await asyncio.sleep(self.poll_seconds)

    async def _run_once(self, service: TaskService) -> None:
        next_task = await service.claim_next_task(self.stale_after_seconds, self.worker_task_types_set)
        if next_task is not None:
            await service.execute_task(next_task)
