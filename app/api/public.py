from __future__ import annotations

import base64
import json
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.models import Article, Feed

router = APIRouter(prefix="/v1", tags=["public"])

def _encode_cursor(slot_date: str, article_id: int) -> str:
    payload = {"s": slot_date, "id": article_id}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

def _decode_cursor(cursor: str) -> tuple[str, int]:
    pad = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode((cursor + pad).encode("utf-8"))
    obj = json.loads(raw.decode("utf-8"))
    return obj["s"], int(obj["id"])

def _preview(markdown: str, max_words: int) -> str:
    words = markdown.split()
    if len(words) <= max_words:
        return markdown
    return " ".join(words[:max_words]) + " …"

@router.get("/articles")
async def list_articles(
    limit: int = Query(default=20, ge=1, le=50),
    cursor: Optional[str] = Query(default=None),
):
    from app.core.db import SessionLocal
    async with SessionLocal() as session:
        stmt = (
            select(Article)
            .options(joinedload(Article.feed))
            .order_by(desc(Article.slot_date), desc(Article.id))
            .limit(limit + 1)
        )

        if cursor:
            try:
                c_slot, c_id = _decode_cursor(cursor)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid cursor")
            # slot_date desc, id desc: fetch records after cursor => where (slot_date < c_slot) OR (slot_date == c_slot AND id < c_id)
            stmt = stmt.where(
                (Article.slot_date < c_slot) | ((Article.slot_date == c_slot) & (Article.id < c_id))
            )

        rows = (await session.execute(stmt)).scalars().all()
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = _encode_cursor(last.slot_date, last.id)
            rows = rows[:limit]

        items = []
        for a in rows:
            items.append(
                {
                    "id": a.id,
                    "slot_date": a.slot_date,
                    "title": a.title,
                    "source_url": a.source_url,
                    "image_url": a.image_url,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                    "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
                    "word_count": a.word_count,
                    "preview_markdown": _preview(a.body_markdown, settings.preview_words),
                    "feed": {
                        "id": a.feed.id,
                        "name": a.feed.name,
                        "url": a.feed.url,
                    },
                }
            )

        return {"items": items, "next_cursor": next_cursor}

@router.get("/articles/{article_id}")
async def get_article(
    article_id: int,
    max_words: Optional[int] = Query(default=None, ge=1, le=5000),
):
    from app.core.db import SessionLocal
    async with SessionLocal() as session:
        stmt = select(Article).options(joinedload(Article.feed)).where(Article.id == article_id)
        a = (await session.execute(stmt)).scalars().first()
        if not a:
            raise HTTPException(status_code=404, detail="Article not found")

        body = a.body_markdown
        if max_words:
            words = body.split()
            if len(words) > max_words:
                body = " ".join(words[:max_words]) + " …"

        return {
            "id": a.id,
            "slot_date": a.slot_date,
            "title": a.title,
            "source_url": a.source_url,
            "image_url": a.image_url,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
            "word_count": a.word_count,
            "body_markdown": body,
            "feed": {
                "id": a.feed.id,
                "name": a.feed.name,
                "url": a.feed.url,
            },
        }
