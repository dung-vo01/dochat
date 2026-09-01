from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document
from app.schemas import DocumentResponse


async def create_document(
    db: AsyncSession, conversation_id: int, filename: str, chunk_count: int
) -> DocumentResponse:
    document = Document(
        conversation_id=conversation_id, filename=filename, chunk_count=chunk_count
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    return DocumentResponse.model_validate(document)


async def list_documents(
    db: AsyncSession, conversation_id: int
) -> list[DocumentResponse]:
    result = await db.execute(
        select(Document)
        .filter(Document.conversation_id == conversation_id)
        .order_by(Document.created_at.asc())
    )

    return [DocumentResponse.model_validate(doc) for doc in result.scalars().all()]


async def get_document(db: AsyncSession, document_id: int) -> Document:
    document = await db.get(Document, document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


async def delete_document(db: AsyncSession, document_id: int) -> None:
    document = await get_document(db, document_id)

    await db.delete(document)
    await db.commit()
