from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import ConversationCreate, ConversationDetail, ConversationResponse
from app.services import memory

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationResponse])
async def list_conversations_api(db: AsyncSession = Depends(get_db)):
    return await memory.get_conversations(db)


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation_api(
    body: ConversationCreate, db: AsyncSession = Depends(get_db)
):
    return await memory.create_conversation(db, title=body.title)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_api(
    conversation_id: int, db: AsyncSession = Depends(get_db)
):
    conversation = await memory.get_conversation(db, conversation_id)

    return conversation


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation_api(
    conversation_id: int, db: AsyncSession = Depends(get_db)
):
    await memory.delete_conversation(db, conversation_id)
