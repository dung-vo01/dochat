import pytest

from app.core.config import settings
from app.services import rag
from app.services.rag import (
    RetrievalResult,
    RetrievedChunk,
    build_system_prompt,
    retrieve,
)


class FakeCollection:
    """Just enough of a Chroma collection: rows are (text, metadata, distance)."""

    def __init__(self, rows):
        self.rows = rows
        self.last_where = None

    def _matching(self, where):
        self.last_where = where
        return [
            r for r in self.rows if r[1]["conversation_id"] == where["conversation_id"]
        ]

    def get(self, where, include=None):
        rows = self._matching(where)
        return {"documents": [r[0] for r in rows], "metadatas": [r[1] for r in rows]}

    def query(self, query_embeddings, n_results, where, include=None):
        rows = sorted(self._matching(where), key=lambda r: r[2])[:n_results]
        return {
            "documents": [[r[0] for r in rows]],
            "metadatas": [[r[1] for r in rows]],
            "distances": [[r[2] for r in rows]],
        }


def row(text, conv=1, filename="a.pdf", page=1, index=0, distance=0.5):
    meta = {
        "conversation_id": conv,
        "filename": filename,
        "page": page,
        "chunk_index": index,
    }
    return (text, meta, distance)


@pytest.fixture
def fake_embed(monkeypatch):
    async def embed(texts):
        return [[0.0] for _ in texts]

    monkeypatch.setattr(rag, "embed", embed)


def use(monkeypatch, rows) -> FakeCollection:
    collection = FakeCollection(rows)
    monkeypatch.setattr(rag, "get_collection", lambda: collection)
    return collection


async def test_retrieval_is_scoped_to_the_conversation(monkeypatch, fake_embed):
    collection = use(monkeypatch, [row("mine", conv=1), row("someone else's", conv=2)])

    result = await retrieve("question", conversation_id=1)

    assert [c.text for c in result.chunks] == ["mine"]
    assert collection.last_where == {"conversation_id": 1}


async def test_returns_nearest_chunks_up_to_top_k(monkeypatch, fake_embed):
    rows = [row(f"chunk {i}", index=i, distance=i / 10) for i in range(10)]
    use(monkeypatch, rows)

    result = await retrieve("question", conversation_id=1)

    assert len(result.chunks) == settings.RETRIEVAL_TOP_K
    assert result.chunks[0].text == "chunk 0"
    assert result.top_distance == 0.0
    assert result.has_documents


async def test_no_documents_means_no_context(monkeypatch, fake_embed):
    use(monkeypatch, [])

    result = await retrieve("question", conversation_id=1)

    assert result.chunks == []
    assert not result.has_documents
    assert result.top_distance is None


async def test_distance_cutoff_is_off_by_default_and_applies_when_set(
    monkeypatch, fake_embed
):
    use(monkeypatch, [row("near", distance=0.4), row("far", distance=1.4)])

    assert len((await retrieve("q", 1)).chunks) == 2  # no cutoff by default

    monkeypatch.setattr(settings, "RETRIEVAL_MAX_DISTANCE", 1.0)
    result = await retrieve("q", 1)
    assert [c.text for c in result.chunks] == ["near"]
    assert result.candidates == 2  # we still know what the search returned
    assert result.has_documents


async def test_summary_query_returns_document_in_reading_order(monkeypatch, fake_embed):
    rows = [row("third", index=2), row("first", index=0), row("second", index=1)]
    use(monkeypatch, rows)

    result = await retrieve("please summarize this", conversation_id=1)

    assert result.summary_mode
    assert [c.text for c in result.chunks] == ["first", "second", "third"]
    assert all(c.distance is None for c in result.chunks)


async def test_summary_query_is_capped_and_spread_across_the_document(
    monkeypatch, fake_embed
):
    monkeypatch.setattr(settings, "SUMMARY_MAX_CHUNKS", 5)
    use(monkeypatch, [row(f"c{i}", index=i) for i in range(100)])

    result = await retrieve("give me an overview", conversation_id=1)

    assert len(result.chunks) == 5
    indexes = [c.chunk_index for c in result.chunks]
    assert indexes == sorted(indexes)
    assert indexes[-1] > 50  # sampled across the whole document, not just the start
    assert result.candidates == 100


async def test_chunks_indexed_before_metadata_existed_still_work(
    monkeypatch, fake_embed
):
    legacy = ("old text", {"conversation_id": 1}, 0.5)
    use(monkeypatch, [legacy])

    result = await retrieve("question", conversation_id=1)

    assert result.chunks[0].filename == "document"
    assert result.chunks[0].page is None


def result_with(chunks, has_documents=True) -> RetrievalResult:
    return RetrievalResult(
        chunks=chunks,
        candidates=len(chunks),
        top_distance=0.5 if chunks else None,
        summary_mode=False,
        has_documents=has_documents,
        elapsed_ms=1,
    )


def test_prompt_numbers_excerpts_and_labels_their_source():
    chunk = RetrievedChunk("Refunds within 30 days.", "policy.pdf", 2, 0, 0.5)
    prompt = build_system_prompt(result_with([chunk]))

    assert "[1] (policy.pdf, page 2)" in prompt
    assert "Refunds within 30 days." in prompt
    assert "untrusted data" in prompt  # prompt-injection guard is present


def test_prompt_without_matches_but_with_documents_says_so():
    prompt = build_system_prompt(result_with([], has_documents=True))
    assert "nothing in them matched" in prompt


def test_prompt_without_documents_is_a_plain_assistant():
    prompt = build_system_prompt(result_with([], has_documents=False))
    assert "documents" not in prompt
