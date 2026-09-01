from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Document(Base):
    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column(String(255))
    chunk_count: Mapped[int] = mapped_column(Integer)

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="documents"
    )
