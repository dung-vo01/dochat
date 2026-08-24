import logging
import uuid

from chromadb.errors import NotFoundError
from fastapi import APIRouter, HTTPException, UploadFile

from app.clients.chroma import chroma_client, get_collection
from app.services.rag import embed
from app.utils.helpers import chunk_text, extract_text_from_pdf

router = APIRouter(prefix="/api", tags=["upload"])
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_file_api(file: UploadFile):
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()
    text = extract_text_from_pdf(contents)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    chunks = chunk_text(text)
    embeddings = await embed(chunks)
    ids = [str(uuid.uuid4()) for _ in chunks]

    try:
        chroma_client.delete_collection("documents")
    except NotFoundError:
        logger.warning("Collection 'documents' does not exist yet, skipping delete")

    collection = get_collection()
    collection.add(documents=chunks, embeddings=embeddings, ids=ids)

    return {"message": f"Indexed {len(chunks)} chunks."}
