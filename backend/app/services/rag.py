from app.clients.chroma import get_collection
from app.clients.openai import EMBED_MODEL, openai_client

SUMMARY_KEYWORDS = {
    "summarize",
    "summary",
    "overview",
    "what is this",
    "what's this",
    "describe",
    "tell me about",
}


async def embed(texts: list[str]) -> list[list[float]]:
    response = await openai_client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def is_summary_query(query: str) -> bool:
    return any(kw in query.lower() for kw in SUMMARY_KEYWORDS)


async def retrieve(query: str, conversation_id: int, n_results: int = 3) -> list[str]:
    collection = get_collection()
    where = {"conversation_id": conversation_id}

    if is_summary_query(query):
        results = collection.get(where=where)
        return results["documents"] if results["documents"] else []

    query_embedding = (await embed([query]))[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
    )
    return results["documents"][0] if results["documents"] else []


def build_system_prompt(context_chunks: list[str]) -> str:
    if not context_chunks:
        return "You are a helpful assistant."

    context_text = "\n\n---\n\n".join(context_chunks)
    return f"""You are a helpful assistant. Answer questions based on the context below.
            If the answer isn't in the context, say so — don't make things up.

            Context:
            {context_text}"""
