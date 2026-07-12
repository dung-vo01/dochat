import uuid
from flask import Blueprint, request
from app.clients.chroma import chroma_client, get_collection
from app.services.rag import embed
from app.utils.helpers import chunk_text, extract_text_from_pdf

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("", methods=["POST"])
def upload():
    if "file" not in request.files:
        return {"error": "No file provided"}, 400

    file = request.files["file"]
    if not file.filename.endswith(".pdf"):
        return {"error": "Only PDF files are supported"}, 400

    text = extract_text_from_pdf(file)
    if not text.strip():
        return {"error": "Could not extract text from PDF"}, 400

    chunks = chunk_text(text)
    embeddings = embed(chunks)
    ids = [str(uuid.uuid4()) for _ in chunks]

    # Wipe old data and recreate fresh, ensures no bleed from previous uploads
    try:
        chroma_client.delete_collection("documents")
    except Exception:
        pass

    collection = get_collection()
    collection.add(documents=chunks, embeddings=embeddings, ids=ids)

    return {"message": f"Indexed {len(chunks)} chunks."}, 200
