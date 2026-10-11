from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.chroma import get_collection
from app.db.session import get_db
from app.schemas import DocumentResponse
from app.services import documents as documents_service
from app.services.ingest import IngestError, ingest_pdf
from app.services.memory import get_conversation

router = APIRouter(prefix="/api", tags=["documents"])


@router.post(
    "/conversations/{conversation_id}/documents",
    response_model=DocumentResponse,
    status_code=201,
)
async def upload_document_api(
    conversation_id: int, file: UploadFile, db: AsyncSession = Depends(get_db)
):
    await get_conversation(db, conversation_id)  # raises 404 if missing

    try:
        return await ingest_pdf(
            db, conversation_id, file.filename or "", await file.read()
        )
    except IngestError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    get_collection().delete(where={"document_id": document_id})

    await documents_service.delete_document(db, document_id)
