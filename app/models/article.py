from __future__ import annotations

from sqlalchemy import String, Integer, DateTime, ForeignKey, func, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("normalized_url", name="uq_articles_normalized_url"),
        UniqueConstraint("slot_date", name="uq_articles_slot_date"),
        Index("ix_articles_slot_date_desc", "slot_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    feed_id: Mapped[int] = mapped_column(Integer, ForeignKey("feeds.id"), nullable=False)
    feed = relationship("Feed")

    guid: Mapped[str | None] = mapped_column(String, nullable=True)

    source_url: Mapped[str] = mapped_column(String, nullable=False)
    normalized_url: Mapped[str] = mapped_column(String, nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)

    published_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Slot date (UTC date string YYYY-MM-DD) - enforces "one per day"
    slot_date: Mapped[str] = mapped_column(String, nullable=False)

    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
