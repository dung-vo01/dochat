from app.clients.openai import openai_client, EMBED_MODEL
from app.clients.chroma import get_collection

# To recognize "summary" intention
SUMMARY_KEYWORDS = {
    "summarize",
    "summary",
    "overview",
    "what is this",
    "what's this",
    "describe",
    "tell me about",
}


def embed(texts: list[str]) -> list[list[float]]:
    response = openai_client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def is_summary_query(query: str) -> bool:
    return any(kw in query.lower() for kw in SUMMARY_KEYWORDS)


def retrieve(query: str, n_results: int = 3) -> list[str]:
    collection = get_collection()

    if is_summary_query(query):
        results = collection.get()
        return results["documents"] if results["documents"] else []

    query_embedding = embed([query])[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
    )
    return results["documents"][0] if results["documents"] else []


def build_system_prompt(context_chunks: list[str]) -> str:
    if not context_chunks:
        return "You are a helpful assistant."

    context_text = "\n\n---\n\n".join(context_chunks)
    return f"""
        You are a helpful assistant. Answer questions based on the context below.
        If the answer isn't in the context, say so and don't make things up.

        Context:
        {context_text}
    """
