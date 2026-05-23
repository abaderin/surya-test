import uuid

import pytest

from app.api.files import _load_task_status_counts
from app.models.enums import TaskStatus


class _FakeResult:
    def __init__(self, rows: list[tuple[uuid.UUID, TaskStatus, int]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[uuid.UUID, TaskStatus, int]]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[tuple[uuid.UUID, TaskStatus, int]]) -> None:
        self._rows = rows

    async def execute(self, _query):
        return _FakeResult(self._rows)


@pytest.mark.asyncio
async def test_load_task_status_counts_returns_only_new_done_failed_and_fills_zeroes() -> None:
    first = uuid.uuid4()
    second = uuid.uuid4()
    fake_db = _FakeSession(
        rows=[
            (first, TaskStatus.NEW, 4),
            (first, TaskStatus.DONE, 7),
            (first, TaskStatus.FAILED, 2),
            (first, TaskStatus.CANCELLED, 9),
        ]
    )

    counts = await _load_task_status_counts(fake_db, [first, second])

    assert counts[first] == {"new": 4, "done": 7, "failed": 2}
    assert counts[second] == {"new": 0, "done": 0, "failed": 0}
