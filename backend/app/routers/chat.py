from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import ChatRequest
from app.services import chat
from app.services.memory import get_conversation

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def stream_chat_api(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    # Validate before the stream starts
    await get_conversation(db, body.conversation_id)

    return StreamingResponse(
        chat.stream_chat(body, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
