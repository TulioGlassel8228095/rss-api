from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.security import require_admin
from app.models import Feed
from app.services.ingest import backfill_slots, ingest_for_slot

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])

class FeedCreate(BaseModel):
    url: HttpUrl
    name: Optional[str] = None
    enabled: bool = True

class FeedUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None

@router.get("/feeds")
async def list_feeds():
    async with SessionLocal() as session:
        feeds = (await session.execute(select(Feed).order_by(Feed.id.asc()))).scalars().all()
        return [
            {
                "id": f.id,
                "url": f.url,
                "name": f.name,
                "enabled": f.enabled,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "last_fetched_at": f.last_fetched_at.isoformat() if f.last_fetched_at else None,
            }
            for f in feeds
        ]

@router.post("/feeds")
async def create_feed(payload: FeedCreate):
    async with SessionLocal() as session:
        feed = Feed(url=str(payload.url), name=payload.name, enabled=payload.enabled)
        session.add(feed)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Feed already exists")
        await session.refresh(feed)
        return {"id": feed.id, "url": feed.url, "name": feed.name, "enabled": feed.enabled}

@router.patch("/feeds/{feed_id}")
async def update_feed(feed_id: int, payload: FeedUpdate):
    async with SessionLocal() as session:
        feed = (await session.execute(select(Feed).where(Feed.id == feed_id))).scalars().first()
        if not feed:
            raise HTTPException(status_code=404, detail="Feed not found")
        if payload.name is not None:
            feed.name = payload.name
        if payload.enabled is not None:
            feed.enabled = payload.enabled
        await session.commit()
        return {"id": feed.id, "url": feed.url, "name": feed.name, "enabled": feed.enabled}

@router.delete("/feeds/{feed_id}")
async def delete_feed(feed_id: int):
    async with SessionLocal() as session:
        res = await session.execute(delete(Feed).where(Feed.id == feed_id))
        await session.commit()
        if res.rowcount == 0:
            raise HTTPException(status_code=404, detail="Feed not found")
        return {"ok": True}

@router.post("/fetch")
async def admin_fetch(
    days: int = Query(default=1, ge=1, le=365),
    end_date: Optional[str] = Query(default=None, description="UTC date YYYY-MM-DD (optional)"),
    max_items_per_feed: int = Query(default=50, ge=1, le=200),
):
    # Backfill slots for last N days, including end_date (or today UTC)
    end_d = None
    if end_date:
        try:
            end_d = dt.date.fromisoformat(end_date)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end_date, must be YYYY-MM-DD")

    async with SessionLocal() as session:
        result = await backfill_slots(session, days=days, end_date_utc=end_d, max_items_per_feed=max_items_per_feed)
        return result

@router.post("/fetch/today")
async def admin_fetch_today(
    max_items_per_feed: int = Query(default=50, ge=1, le=200),
):
    slot = dt.datetime.now(dt.timezone.utc).date().isoformat()
    async with SessionLocal() as session:
        st = await ingest_for_slot(session, slot_date=slot, max_items_per_feed=max_items_per_feed)
        return {
            "slot_date": slot,
            "feeds_processed": st.feeds_processed,
            "items_seen": st.items_seen,
            "inserted": st.inserted,
            "duplicates": st.duplicates,
            "skipped": st.skipped,
            "errors": st.errors,
        }
