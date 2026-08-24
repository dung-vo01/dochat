from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import ChatRequest
from app.services import chat

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def stream_chat_api(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        return StreamingResponse(
            chat.stream_chat(body, db),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
