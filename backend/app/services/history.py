"""Conversation memory: keep the prompt bounded as conversations grow."""

import re

CITATION_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def estimate_tokens(text: str) -> int:
    """~4 chars per token (+ a little per-message overhead).

    Deliberately approximate: the budget exists to bound cost and latency, well
    below the model's context limit, so a tokenizer's exactness isn't worth the
    extra dependency or its cold-start download.
    """
    return len(text) // 4 + 4


def trim_history(messages: list[dict], budget: int) -> tuple[list[dict], int]:
    """Keep the most recent messages that fit in `budget` tokens.

    The newest message is always kept. Returns (kept, number_dropped). Dropped
    turns are simply forgotten - a rolling summary would be the next step.
    """
    kept: list[dict] = []
    used = 0

    for message in reversed(messages):
        cost = estimate_tokens(message["content"])
        if kept and used + cost > budget:
            break
        kept.append(message)
        used += cost

    kept.reverse()

    # Don't open with an assistant reply whose question was trimmed away.
    while len(kept) > 1 and kept[0]["role"] != "user":
        kept.pop(0)

    return kept, len(messages) - len(kept)


def cited_numbers(answer: str) -> list[int]:
    """Excerpt numbers the model cited, e.g. 'see [1][3]' or '[1, 2]' -> [1, 2, 3]."""
    numbers: set[int] = set()
    for group in CITATION_RE.findall(answer):
        numbers.update(int(n) for n in re.split(r"\s*,\s*", group))
    return sorted(numbers)


FOLLOW_UP_MAX_WORDS = 8


def contextualise_query(message: str, previous_user_message: str | None) -> str:
    """Make a short follow-up searchable on its own.

    "And for Enterprise?" embeds far from the chunk that answers it, because the
    subject lives in the previous turn. Prepending that turn pulls the query back
    toward the right chunk (see evals/retrieval_sweep.py --contextualise). A cheap
    heuristic rather than an LLM rewrite: no extra call, no extra latency.
    """
    if previous_user_message and len(message.split()) <= FOLLOW_UP_MAX_WORDS:
        return f"{previous_user_message} {message}"
    return message
