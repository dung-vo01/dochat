"""Retrieval-only sweep: pick chunk size / top-k / distance threshold from data.

Run from backend/:  uv run python -m evals.retrieval_sweep

For every golden case that has a `gold_phrase`, finds where the chunk containing
that phrase ranks for the question (no LLM generation involved, so it's cheap and
deterministic), for several chunk sizes. It also prints the distance of the best
match for unanswerable questions, which is what a relevance threshold has to
separate from "correct chunk" distances.

`--contextualise` additionally tries the cheap follow-up fix of prepending the
previous user turn to the query before embedding.
"""

import argparse
import asyncio
import statistics
from pathlib import Path

from app.clients.chroma import get_collection
from app.db.session import async_session_maker
from app.services.ingest import ingest_pdf
from app.services.memory import create_conversation, delete_conversation
from app.services.rag import embed
from evals.run_evals import DEFAULT_FIXTURES, DEFAULT_GOLDEN, load_cases, normalise

SIZES = [300, 500, 800, 1200]
KS = [1, 3, 4, 6]


def query_text(case: dict, contextualise: bool) -> str:
    setup = case.get("setup_turns")
    if contextualise and setup:
        return f"{setup[-1]} {case['question']}"
    return case["question"]


async def sweep(
    size: int, cases: list[dict], vectors: dict[str, list[float]], contextualise: bool
):
    overlap = round(size * 0.3)
    async with async_session_maker() as db:
        conv = await create_conversation(db, title=f"sweep-{size}")
        try:
            for fixture in DEFAULT_FIXTURES:
                await ingest_pdf(
                    db,
                    conv.id,
                    fixture.name,
                    fixture.read_bytes(),
                    chunk_size=size,
                    chunk_overlap=overlap,
                )

            collection = get_collection()
            ranks: dict[str, int | None] = {}
            gold_dist: dict[str, float] = {}
            unanswerable_top: dict[str, float] = {}

            for case in cases:
                q = query_text(case, contextualise)
                found = collection.query(
                    query_embeddings=[vectors[q]],
                    n_results=10,
                    where={"conversation_id": conv.id},
                    include=["documents", "distances"],
                )
                docs, dists = found["documents"][0], found["distances"][0]

                if case.get("expect_refusal"):
                    unanswerable_top[case["id"]] = dists[0]
                    continue
                gold = case.get("gold_phrase")
                if not gold:
                    continue
                rank = next(
                    (
                        i
                        for i, d in enumerate(docs, 1)
                        if normalise(gold) in normalise(d)
                    ),
                    None,
                )
                ranks[case["id"]] = rank
                if rank:
                    gold_dist[case["id"]] = dists[rank - 1]

            n_chunks = collection.count()  # all conversations; informational
            return ranks, gold_dist, unanswerable_top, n_chunks
        finally:
            await delete_conversation(db, conv.id)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--contextualise", action="store_true")
    args = parser.parse_args()

    cases = load_cases(args.golden)
    queries = sorted({query_text(c, args.contextualise) for c in cases})
    vectors = dict(zip(queries, await embed(queries), strict=True))

    print(
        f"query mode: {'contextualised follow-ups' if args.contextualise else 'raw last message'}\n"
    )
    print(
        f"{'size':>5} "
        + " ".join(f"hit@{k:<2}" for k in KS)
        + "  gold dist (median / max)   unanswerable top-1 (min)"
    )

    last = None
    for size in SIZES:
        ranks, gold_dist, unans, _ = await sweep(
            size, cases, vectors, args.contextualise
        )
        n = len(ranks)
        hits = [sum(1 for r in ranks.values() if r and r <= k) / n for k in KS]
        dvals = list(gold_dist.values())
        print(
            f"{size:>5} "
            + " ".join(f"{h * 100:>5.0f}%" for h in hits)
            + f"   {statistics.median(dvals):.2f} / {max(dvals):.2f}"
            + f"                 {min(unans.values()):.2f}"
        )
        last = (size, ranks, gold_dist, unans)

    # Show the per-case detail for the largest size so misses are easy to inspect.
    size, ranks, gold_dist, unans = last
    print(f"\nper-case at chunk size {size}:")
    for case_id, rank in ranks.items():
        d = gold_dist.get(case_id)
        print(
            f"  {case_id:32} rank={rank!s:>4} dist={'-' if d is None else f'{d:.2f}'}"
        )
    for case_id, d in unans.items():
        print(f"  {case_id:32} (unanswerable) top-1 dist={d:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
