import asyncio

from app.worker.loop import WorkerLoop


async def main() -> None:
    loop = WorkerLoop()
    await loop.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        await loop.stop()


if __name__ == "__main__":
    asyncio.run(main())
