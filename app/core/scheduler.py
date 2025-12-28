from __future__ import annotations

import datetime as dt
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import SessionLocal
from app.services.ingest import ingest_for_slot

scheduler = AsyncIOScheduler(timezone=dt.timezone.utc)

def _parse_hhmm(s: str) -> tuple[int, int]:
    parts = s.strip().split(":")
    if len(parts) != 2:
        raise ValueError("FETCH_AT_UTC must be HH:MM")
    return int(parts[0]), int(parts[1])

async def run_daily_job() -> None:
    # Fill today's slot (UTC)
    slot_date = dt.datetime.now(dt.timezone.utc).date().isoformat()
    async with SessionLocal() as session:
        await ingest_for_slot(session, slot_date=slot_date, max_items_per_feed=settings.max_items_per_feed)

def start_scheduler() -> None:
    hour, minute = _parse_hhmm(settings.fetch_at_utc)
    scheduler.add_job(
        run_daily_job,
        CronTrigger(hour=hour, minute=minute),
        id="daily_ingest",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()

def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
