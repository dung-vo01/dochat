from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatTurn(Base):
    """One row per user question answered (or failed). The raw material for the
    metrics dashboard: latency, retrieval quality, tool use, tokens, errors.

    `conversation_id` is deliberately NOT a foreign key: deleting a conversation
    must not erase the operational history of the system.
    """

    __tablename__ = "chat_turns"

    conversation_id: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(
        String(20), default="app", index=True
    )  # app | eval
    model: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))  # ok | error | cancelled
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    latency_ms: Mapped[int] = mapped_column(Integer)
    ttft_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrieval_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Retrieval quality signals
    retrieved_chunks: Mapped[int] = mapped_column(Integer, default=0)
    used_chunks: Mapped[int] = mapped_column(
        Integer, default=0
    )  # passed the relevance threshold
    top_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    has_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    cited_sources: Mapped[int] = mapped_column(Integer, default=0)

    tool_called: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_blocked: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # gate refused a tool call
    history_messages: Mapped[int] = mapped_column(Integer, default=0)
    history_trimmed: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
