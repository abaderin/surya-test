from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.enums import TaskType
from app.worker.loop import WorkerLoop


@pytest.mark.asyncio
async def test_run_once_claims_and_executes_task() -> None:
    service = AsyncMock()
    service.claim_next_task.return_value = SimpleNamespace(id="task-1")
    loop = WorkerLoop(
        poll_seconds=0.01,
        stale_after_seconds=120,
        worker_task_types_set={TaskType.LAYOUT},
        cpu_threads=1,
    )

    await loop._run_once(service)

    service.claim_next_task.assert_awaited_once_with(120, {TaskType.LAYOUT})
    service.execute_task.assert_awaited_once_with(service.claim_next_task.return_value)


@pytest.mark.asyncio
async def test_run_once_skips_execute_when_no_task() -> None:
    service = AsyncMock()
    service.claim_next_task.return_value = None
    loop = WorkerLoop(
        poll_seconds=0.01,
        stale_after_seconds=120,
        worker_task_types_set={TaskType.OCR},
        cpu_threads=1,
    )

    await loop._run_once(service)

    service.claim_next_task.assert_awaited_once_with(120, {TaskType.OCR})
    service.execute_task.assert_not_awaited()
