from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.files import router as files_router
from app.api.media import router as media_router
from app.api.tasks import router as tasks_router
from app.api.ws import router as ws_router
from app.core.settings import settings
from app.worker.loop import WorkerLoop

worker_loop: WorkerLoop | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker_loop
    if settings.worker_enabled:
        worker_loop = WorkerLoop()
        await worker_loop.start()
    yield
    if worker_loop:
        await worker_loop.stop()


app = FastAPI(title="Surya Inspector API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(files_router)
app.include_router(media_router)
app.include_router(tasks_router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
