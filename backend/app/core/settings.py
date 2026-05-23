from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.enums import TaskType


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://surya:surya@127.0.0.1:5433/surya"
    redis_url: str = "redis://127.0.0.1:6379/0"
    storage_root: str | None = None
    media_root: str | None = None
    max_upload_mb: int = 100
    worker_enabled: bool = False
    worker_poll_seconds: float = 1.0
    worker_stale_after_seconds: int = 120
    worker_task_types: str | None = None
    cpu_threads: int = 1
    page_render_dpi: int = 300
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    @property
    def storage_root_path(self) -> Path:
        chosen = self.storage_root or self.media_root or "./storage"
        return Path(chosen).resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def worker_task_types_set(self) -> set[TaskType] | None:
        if not self.worker_task_types:
            return None
        values = [item.strip() for item in self.worker_task_types.split(",") if item.strip()]
        if not values:
            return None
        return {TaskType(value) for value in values}

    @model_validator(mode="after")
    def _normalize_storage(self) -> "Settings":
        if self.storage_root is None and self.media_root is not None:
            self.storage_root = self.media_root
        if self.cpu_threads < 1:
            raise ValueError("CPU_THREADS must be >= 1")
        if self.page_render_dpi < 72:
            raise ValueError("PAGE_RENDER_DPI must be >= 72")
        return self


settings = Settings()
