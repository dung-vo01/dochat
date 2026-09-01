import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.chroma import get_collection
from app.db.session import get_db
from app.schemas import DocumentResponse
from app.services import documents as documents_service
from app.services.memory import get_conversation
from app.services.rag import embed
from app.utils.helpers import chunk_text, extract_text_from_pdf

router = APIRouter(prefix="/api", tags=["documents"])


@router.post(
    "/conversations/{conversation_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
)
async def upload_document_api(
    conversation_id: int, file: UploadFile, db: AsyncSession = Depends(get_db)
):
    await get_conversation(db, conversation_id)

    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()
    text = extract_text_from_pdf(contents)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    chunks = chunk_text(text)
    embeddings = await embed(chunks)

    document = await documents_service.create_document(
        db, conversation_id, file.filename, len(chunks)
    )

    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [
        {"conversation_id": conversation_id, "document_id": document.id} for _ in chunks
    ]

    collection = get_collection()
    collection.add(
        documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas
    )

    return document


@router.get(
    "/conversations/{conversation_id}/documents",
    response_model=list[DocumentResponse],
)
async def list_documents_api(conversation_id: int, db: AsyncSession = Depends(get_db)):
    await get_conversation(db, conversation_id)  # raises 404 if missing

    return await documents_service.list_documents(db, conversation_id)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document_api(document_id: int, db: AsyncSession = Depends(get_db)):
    await documents_service.get_document(db, document_id)  # raises 404 if missing

    # Delete the vectors before the DB row: if this fails partway, the document
    # stays visible with a dangling reference rather than orphaning searchable
    # vectors that no longer show up anywhere in the UI
    collection = get_collection()
    collection.delete(where={"document_id": document_id})

    await documents_service.delete_document(db, document_id)
