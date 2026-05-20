from fastapi import APIRouter

from app.api.files import media_file

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{path:path}")
async def media(path: str):
    return await media_file(path)
