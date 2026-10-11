"""Per-turn tracing and the queries behind the metrics dashboard.

Every chat turn produces one `ChatTurn` row. The dashboard answers the question
"how do I know it's working today?" - latency, time-to-first-token, error rate,
how often retrieval found nothing relevant, which tools fire, token usage.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.chroma import get_collection
from app.db.session import async_session_maker
from app.models import ChatTurn, Conversation, Document

logger = logging.getLogger(__name__)


@dataclass
class TurnTrace:
    conversation_id: int
    source: str
    model: str
    started: float = field(default_factory=time.perf_counter)

    status: str = "ok"
    error_type: str | None = None
    error_message: str | None = None
    ttft_ms: int | None = None
    retrieval_ms: int | None = None
    retrieved_chunks: int = 0
    used_chunks: int = 0
    top_distance: float | None = None
    summary_mode: bool = False
    has_documents: bool = False
    cited_sources: int = 0
    tool_called: str | None = None
    tool_blocked: bool = False
    history_messages: int = 0
    history_trimmed: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    def mark_first_token(self) -> None:
        if self.ttft_ms is None:
            self.ttft_ms = int((time.perf_counter() - self.started) * 1000)

    def add_usage(self, usage) -> None:
        self.prompt_tokens = (self.prompt_tokens or 0) + (usage.prompt_tokens or 0)
        self.completion_tokens = (self.completion_tokens or 0) + (
            usage.completion_tokens or 0
        )

    def apply_retrieval(self, result) -> None:
        self.retrieval_ms = result.elapsed_ms
        self.retrieved_chunks = result.candidates
        self.used_chunks = len(result.chunks)
        self.top_distance = result.top_distance
        self.summary_mode = result.summary_mode
        self.has_documents = result.has_documents

    def fail(self, exc: Exception, message: str) -> None:
        self.status = "error"
        self.error_type = type(exc).__name__
        self.error_message = message[:500]

    def to_row(self) -> ChatTurn:
        return ChatTurn(
            conversation_id=self.conversation_id,
            source=self.source,
            model=self.model,
            status=self.status,
            error_type=self.error_type,
            error_message=self.error_message,
            latency_ms=int((time.perf_counter() - self.started) * 1000),
            ttft_ms=self.ttft_ms,
            retrieval_ms=self.retrieval_ms,
            retrieved_chunks=self.retrieved_chunks,
            used_chunks=self.used_chunks,
            top_distance=self.top_distance,
            summary_mode=self.summary_mode,
            has_documents=self.has_documents,
            cited_sources=self.cited_sources,
            tool_called=self.tool_called,
            tool_blocked=self.tool_blocked,
            history_messages=self.history_messages,
            history_trimmed=self.history_trimmed,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
        )


async def record_turn(trace: TurnTrace) -> None:
    """Persist a turn in its own session. Never raises: metrics must not break chat."""
    try:
        row = trace.to_row()
        async with async_session_maker() as session:
            session.add(row)
            await session.commit()

        logger.info(
            "chat_turn %s",
            json.dumps(
                {
                    "conversation_id": row.conversation_id,
                    "source": row.source,
                    "status": row.status,
                    "latency_ms": row.latency_ms,
                    "ttft_ms": row.ttft_ms,
                    "retrieval_ms": row.retrieval_ms,
                    "used_chunks": row.used_chunks,
                    "top_distance": row.top_distance,
                    "tool": row.tool_called,
                    "tool_blocked": row.tool_blocked,
                    "tokens": [row.prompt_tokens, row.completion_tokens],
                    "error_type": row.error_type,
                }
            ),
        )
    except Exception:
        logger.exception("failed to record chat turn metrics")


def _pct(column, fraction: float):
    return func.percentile_cont(fraction).within_group(column)


def _num(value) -> float | None:
    return None if value is None else float(value)


async def summary(db: AsyncSession, hours: int = 24, source: str = "app") -> dict:
    since = datetime.now(UTC) - timedelta(hours=hours)
    window = and_(ChatTurn.created_at >= since, ChatTurn.source == source)

    row = (
        await db.execute(
            select(
                func.count().label("turns"),
                func.count().filter(ChatTurn.status == "error").label("errors"),
                func.count().filter(ChatTurn.status == "cancelled").label("cancelled"),
                _pct(ChatTurn.latency_ms, 0.5).label("lat_p50"),
                _pct(ChatTurn.latency_ms, 0.95).label("lat_p95"),
                _pct(ChatTurn.ttft_ms, 0.5).label("ttft_p50"),
                _pct(ChatTurn.ttft_ms, 0.95).label("ttft_p95"),
                func.avg(ChatTurn.prompt_tokens).label("avg_prompt"),
                func.avg(ChatTurn.completion_tokens).label("avg_completion"),
                func.count().filter(ChatTurn.has_documents).label("doc_turns"),
                func.count()
                .filter(
                    and_(
                        ChatTurn.has_documents,
                        ChatTurn.used_chunks == 0,
                        ChatTurn.summary_mode.is_(False),
                    )
                )
                .label("no_match"),
                func.avg(ChatTurn.top_distance).label("avg_top_distance"),
                func.count().filter(ChatTurn.tool_blocked).label("tools_blocked"),
                func.count().filter(ChatTurn.history_trimmed > 0).label("trimmed"),
            ).where(window)
        )
    ).one()

    tools = (
        await db.execute(
            select(ChatTurn.tool_called, func.count())
            .where(window, ChatTurn.tool_called.is_not(None))
            .group_by(ChatTurn.tool_called)
        )
    ).all()

    bucket_unit = "hour" if hours <= 48 else "day"
    bucket = func.date_trunc(bucket_unit, ChatTurn.created_at).label("bucket")
    series = (
        await db.execute(
            select(
                bucket,
                func.count().label("turns"),
                func.count().filter(ChatTurn.status == "error").label("errors"),
                _pct(ChatTurn.latency_ms, 0.5).label("p50"),
            )
            .where(window)
            .group_by(bucket)
            .order_by(bucket)
        )
    ).all()

    totals = {
        "conversations": await db.scalar(
            select(func.count()).select_from(Conversation)
        ),
        "documents": await db.scalar(select(func.count()).select_from(Document)),
        "indexed_chunks": get_collection().count(),
    }

    turns = row.turns or 0
    return {
        "window_hours": hours,
        "turns": turns,
        "error_rate": (row.errors / turns) if turns else None,
        "cancelled_rate": (row.cancelled / turns) if turns else None,
        "latency_ms": {"p50": _num(row.lat_p50), "p95": _num(row.lat_p95)},
        "ttft_ms": {"p50": _num(row.ttft_p50), "p95": _num(row.ttft_p95)},
        "avg_tokens": {
            "prompt": _num(row.avg_prompt),
            "completion": _num(row.avg_completion),
        },
        # Of turns in conversations that have documents: how many found nothing relevant?
        "no_match_rate": (row.no_match / row.doc_turns) if row.doc_turns else None,
        "avg_top_distance": _num(row.avg_top_distance),
        "tools": {name: count for name, count in tools},
        "tools_blocked": row.tools_blocked,
        "history_trimmed_turns": row.trimmed,
        "series": [
            {
                "bucket": b.isoformat(),
                "turns": t,
                "errors": e,
                "p50_latency_ms": _num(p50),
            }
            for b, t, e, p50 in series
        ],
        "totals": totals,
    }


async def recent(db: AsyncSession, limit: int = 20, source: str = "app") -> list[dict]:
    rows = (
        await db.scalars(
            select(ChatTurn)
            .where(ChatTurn.source == source)
            .order_by(ChatTurn.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "conversation_id": r.conversation_id,
            "status": r.status,
            "latency_ms": r.latency_ms,
            "ttft_ms": r.ttft_ms,
            "used_chunks": r.used_chunks,
            "top_distance": r.top_distance,
            "tool": r.tool_called,
            "tool_blocked": r.tool_blocked,
            "tokens": (r.prompt_tokens or 0) + (r.completion_tokens or 0) or None,
            "error": r.error_message,
        }
        for r in rows
    ]
