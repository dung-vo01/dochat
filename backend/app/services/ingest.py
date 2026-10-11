import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.chroma import get_collection
from app.core.config import settings
from app.schemas import DocumentResponse
from app.services import documents as documents_service
from app.services.rag import embed
from app.utils.helpers import chunk_pages, extract_pages

logger = logging.getLogger(__name__)


class IngestError(ValueError):
    """The upload can't be indexed (wrong type, unreadable, no text, too big)."""


async def ingest_pdf(
    db: AsyncSession,
    conversation_id: int,
    filename: str,
    data: bytes,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> DocumentResponse:
    """Extract -> chunk (per page) -> embed -> index, scoped to one conversation."""
    if not filename.lower().endswith(".pdf"):
        raise IngestError("Only PDF files are supported")

    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise IngestError(f"File is larger than {settings.MAX_UPLOAD_MB} MB")

    try:
        pages = extract_pages(data)
    except Exception as e:  # pypdf raises a zoo of exception types on bad files
        logger.warning("PDF parse failed for %s: %s", filename, e)
        raise IngestError("Could not read this PDF - is it corrupted?") from e

    chunks = chunk_pages(
        pages,
        chunk_size or settings.CHUNK_SIZE,
        chunk_overlap if chunk_overlap is not None else settings.CHUNK_OVERLAP,
    )
    if not chunks:
        raise IngestError(
            "Could not extract text from PDF (scanned/image-only PDFs need OCR)"
        )

    embeddings = await embed([c.text for c in chunks])
    document = await documents_service.create_document(
        db, conversation_id, filename, len(chunks)
    )

    try:
        get_collection().add(
            ids=[str(uuid.uuid4()) for _ in chunks],
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "conversation_id": conversation_id,
                    "document_id": document.id,
                    "filename": filename,
                    "page": c.page,
                    "chunk_index": c.index,
                }
                for c in chunks
            ],
        )
    except Exception:
        # Don't leave a document row that points at vectors that never landed.
        await documents_service.delete_document(db, document.id)
        raise

    return document
