from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.chroma import get_collection
from app.models import Conversation, Message
from app.schemas import ConversationDetail, ConversationResponse, MessageResponse


async def create_conversation(
    db: AsyncSession, title: str = "New chat"
) -> ConversationResponse:
    conversation = Conversation(title=title)

    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    return ConversationResponse.model_validate(conversation)


async def get_conversations(db: AsyncSession) -> list[ConversationResponse]:
    result = await db.execute(
        select(Conversation).order_by(Conversation.created_at.desc())
    )

    return [
        ConversationResponse.model_validate(conversation)
        for conversation in result.scalars().all()
    ]


async def get_conversation(
    db: AsyncSession, conversation_id: int
) -> ConversationDetail | None:
    conversation = await db.get(
        Conversation, conversation_id, options=[selectinload(Conversation.messages)]
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetail.model_validate(conversation)


async def get_messages(db: AsyncSession, conversation_id: int) -> list[MessageResponse]:
    result = await db.execute(
        select(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )

    return [
        MessageResponse.model_validate(message) for message in result.scalars().all()
    ]


async def save_message(
    db: AsyncSession, conversation_id: int, role: str, content: str
) -> MessageResponse:
    message = Message(conversation_id=conversation_id, role=role, content=content)

    db.add(message)
    await db.commit()

    return MessageResponse.model_validate(message)


async def update_conversation_title(
    db: AsyncSession, conversation_id: int, title: str
) -> None:
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(title=title[:50])
    )
    await db.commit()


async def clear_messages(db: AsyncSession, conversation_id: int) -> None:
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.commit()


async def delete_conversation(db: AsyncSession, conversation_id: int) -> None:
    conversation = await db.get(Conversation, conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # The Document rows cascade-delete with the conversation, but their Chroma
    # vectors don't, clean those up explicitly or they'd become permanently
    # orphaned storage
    get_collection().delete(where={"conversation_id": conversation_id})

    await db.delete(conversation)
    await db.commit()
