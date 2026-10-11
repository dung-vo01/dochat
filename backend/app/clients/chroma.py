import chromadb

from app.core.config import settings

chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PATH)


def get_collection():
    return chroma_client.get_or_create_collection(name="documents")
