import asyncio

from app.core.settings import settings
from app.worker.loop import WorkerLoop


async def main() -> None:
    loop = WorkerLoop(
        poll_seconds=settings.worker_poll_seconds,
        stale_after_seconds=settings.worker_stale_after_seconds,
        worker_task_types_set=settings.worker_task_types_set,
    )
    await loop.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        await loop.stop()


if __name__ == "__main__":
    asyncio.run(main())
