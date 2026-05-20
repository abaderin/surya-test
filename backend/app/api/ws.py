import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import get_redis
from app.services.events import EventBus

router = APIRouter(tags=["ws"])


@router.websocket("/api/ws/files/{file_id}")
async def file_ws(websocket: WebSocket, file_id: UUID) -> None:
    await websocket.accept()
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(EventBus.channel(file_id))
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg.get("data"):
                raw = msg["data"]
                payload = raw if isinstance(raw, str) else raw.decode("utf-8")
                await websocket.send_text(payload)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(EventBus.channel(file_id))
        await pubsub.close()
