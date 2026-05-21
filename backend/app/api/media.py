from fastapi import APIRouter, Depends

from app.api.deps import get_storage
from app.api.files import media_file
from app.services.storage import StorageService

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{path:path}")
async def media(path: str, storage: StorageService = Depends(get_storage)):
    return await media_file(path, storage)
