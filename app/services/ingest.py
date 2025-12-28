from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Feed, Article
from app.services.fetcher import Fetcher
from app.services.normalize import normalize_url, sha256_text
from app.services.parser import parse_article

@dataclass
class IngestStats:
    feeds_processed: int = 0
    items_seen: int = 0
    inserted: int = 0
    duplicates: int = 0
    skipped: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def _parse_entry_datetime(entry) -> Optional[dt.datetime]:
    # feedparser exposes: published_parsed / updated_parsed as time.struct_time
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None)
        if t:
            try:
                return dt.datetime(*t[:6], tzinfo=dt.timezone.utc)
            except Exception:
                pass
    return None

def _rss_image(entry) -> Optional[str]:
    # Try common RSS fields
    # media_content
    mc = getattr(entry, "media_content", None)
    if mc and isinstance(mc, list) and mc:
        url = mc[0].get("url")
        if url:
            return url
    # enclosures
    encl = getattr(entry, "enclosures", None)
    if encl and isinstance(encl, list) and encl:
        url = encl[0].get("href") or encl[0].get("url")
        if url:
            return url
    # media_thumbnail
    mt = getattr(entry, "media_thumbnail", None)
    if mt and isinstance(mt, list) and mt:
        url = mt[0].get("url")
        if url:
            return url
    return None

def _rss_encoded_html(entry) -> Optional[str]:
    c = getattr(entry, "content", None)
    if c and isinstance(c, list) and c:
        val = c[0].get("value")
        if val:
            return val
    return None

async def _slot_filled(session: AsyncSession, slot_date: str) -> bool:
    q = select(Article.id).where(Article.slot_date == slot_date).limit(1)
    r = await session.execute(q)
    return r.scalar_one_or_none() is not None

async def _normalized_url_exists(session: AsyncSession, normalized_url: str) -> bool:
    q = select(Article.id).where(Article.normalized_url == normalized_url).limit(1)
    r = await session.execute(q)
    return r.scalar_one_or_none() is not None

async def ingest_for_slot(session: AsyncSession, slot_date: str, max_items_per_feed: int) -> IngestStats:
    stats = IngestStats()

    # If slot already has an article, do nothing
    if await _slot_filled(session, slot_date):
        return stats

    fetcher = Fetcher(settings.user_agent, settings.request_timeout_seconds)

    feeds = (await session.execute(select(Feed).where(Feed.enabled == True))).scalars().all()  # noqa: E712
    # Pull RSS items across all feeds, then pick the newest unseen candidate
    candidates = []
    for feed in feeds:
        try:
            rss = await fetcher.fetch_rss(feed.url, feed.etag, feed.last_modified)
            stats.feeds_processed += 1

            # Update fetch metadata even if empty, except 304
            feed.last_fetched_at = _utc_now()
            if not rss.not_modified:
                feed.etag = rss.etag
                feed.last_modified = rss.last_modified
            await session.commit()

            if rss.not_modified or not rss.parsed:
                continue

            for entry in (rss.parsed.entries or [])[:max_items_per_feed]:
                stats.items_seen += 1
                link = getattr(entry, "link", None)
                title = getattr(entry, "title", None)
                if not link or not title:
                    stats.skipped += 1
                    continue
                published_at = _parse_entry_datetime(entry)
                candidates.append((published_at or _utc_now(), feed, entry))
        except Exception as e:
            stats.errors.append(f"feed {feed.url}: {type(e).__name__}: {e}")

    # Sort newest first
    candidates.sort(key=lambda x: x[0], reverse=True)

    # Try candidates until one inserts successfully
    for published_at, feed, entry in candidates:
        try:
            source_url = entry.link
            normalized = normalize_url(source_url)

            if await _normalized_url_exists(session, normalized):
                stats.duplicates += 1
                continue

            rss_title = getattr(entry, "title", None)
            rss_image = _rss_image(entry)
            encoded_html = _rss_encoded_html(entry)

            page_html = None
            # If no encoded HTML, fetch page
            if not encoded_html:
                html, ctype, status = await fetcher.fetch_page_html(source_url)
                if status in (401, 402, 403, 429):
                    stats.skipped += 1
                    continue
                page_html = html

            parsed = parse_article(
                source_url=source_url,
                rss_title=rss_title,
                rss_image_url=rss_image,
                encoded_html=encoded_html,
                page_html=page_html,
                force_h1_title=True,
            )
            if not parsed:
                stats.skipped += 1
                continue

            if parsed.word_count < settings.min_words:
                stats.skipped += 1
                continue

            art = Article(
                feed_id=feed.id,
                guid=getattr(entry, "id", None),
                source_url=source_url,
                normalized_url=normalized,
                title=parsed.title,
                image_url=parsed.image_url,
                published_at=published_at,
                slot_date=slot_date,
                word_count=parsed.word_count,
                body_markdown=parsed.body_markdown,
                sha256=sha256_text(parsed.body_markdown),
            )

            session.add(art)
            await session.commit()
            stats.inserted += 1
            return stats
        except IntegrityError:
            await session.rollback()
            stats.duplicates += 1
            continue
        except Exception as e:
            await session.rollback()
            stats.errors.append(f"entry {getattr(entry,'link',None)}: {type(e).__name__}: {e}")

    return stats

async def backfill_slots(session: AsyncSession, days: int, end_date_utc: dt.date | None = None, max_items_per_feed: int = 50) -> dict:
    # Fill missing slots for last N days (including end_date)
    if end_date_utc is None:
        end_date_utc = _utc_now().date()

    started_at = _utc_now()
    totals = IngestStats()
    filled = 0

    # Oldest -> newest makes logs nicer, but either is fine
    for i in range(days - 1, -1, -1):
        slot = (end_date_utc - dt.timedelta(days=i)).isoformat()
        st = await ingest_for_slot(session, slot, max_items_per_feed=max_items_per_feed)
        totals.feeds_processed += st.feeds_processed
        totals.items_seen += st.items_seen
        totals.inserted += st.inserted
        totals.duplicates += st.duplicates
        totals.skipped += st.skipped
        totals.errors.extend(st.errors)
        if st.inserted:
            filled += 1

    finished_at = _utc_now()

    return {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "days_requested": days,
        "days_filled": filled,
        "feeds_processed": totals.feeds_processed,
        "items_seen": totals.items_seen,
        "inserted": totals.inserted,
        "duplicates": totals.duplicates,
        "skipped": totals.skipped,
        "errors": totals.errors,
    }
