# RSS Landing Articles API (FastAPI + SQLite)

Features:
- Daily ingestion: **1 article per UTC day** (slot-based)
- RSS parsing -> `content:encoded` preferred -> fallback to page fetch
- Main content extraction (trafilatura, fallback readability-lxml)
- Store **raw Markdown** in SQLite
- Public API (open) for landing pages
- Admin API (token) to manage feeds and trigger fetch/backfill

## Quickstart

1) Copy env:
```bash
cp .env.example .env
```

2) Run:
```bash
docker compose up --build
```

3) Add a feed (admin):
```bash
curl -X POST http://localhost:8000/v1/admin/feeds \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: change_me" \
  -d '{"url":"https://example.com/rss","name":"Example"}'
```

4) Populate DB (admin backfill last 7 slots):
```bash
curl -X POST "http://localhost:8000/v1/admin/fetch?days=7" \
  -H "X-Admin-Token: change_me"
```

5) Public fetch:
```bash
curl "http://localhost:8000/v1/articles?limit=10"
curl "http://localhost:8000/v1/articles/1"
```

## Notes

- **One-per-day rule** is enforced via `slot_date` (UTC date string).
- Scheduler runs daily at `FETCH_AT_UTC` (UTC time), filling **today's slot** if empty.
- Images are **hotlinked** (stored as `image_url` if found, else `null`).
