from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.db import engine
from app.core.scheduler import start_scheduler, shutdown_scheduler
from app.api.public import router as public_router
from app.api.admin import router as admin_router

app = FastAPI(title="RSS Landing Articles API", version="1.0.0")

# Open by default (you asked fully open). Keep CORS permissive for easy landing integration.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(admin_router)

CREATE_TABLES_SQL = [
    '''
    CREATE TABLE IF NOT EXISTS feeds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL UNIQUE,
        name TEXT,
        enabled BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
        last_fetched_at DATETIME,
        etag TEXT,
        last_modified TEXT
    );
    ''',
    '''
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feed_id INTEGER NOT NULL,
        guid TEXT,
        source_url TEXT NOT NULL,
        normalized_url TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        image_url TEXT,
        published_at DATETIME,
        fetched_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
        slot_date TEXT NOT NULL UNIQUE,
        word_count INTEGER NOT NULL,
        body_markdown TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        FOREIGN KEY(feed_id) REFERENCES feeds(id) ON DELETE CASCADE
    );
    ''',
    'CREATE INDEX IF NOT EXISTS ix_articles_slot_date_desc ON articles(slot_date);',
]

@app.on_event("startup")
async def on_startup():
    # Create tables (simple, no migration tool needed for MVP)
    async with engine.begin() as conn:
        for stmt in CREATE_TABLES_SQL:
            await conn.execute(text(stmt))
    start_scheduler()

@app.on_event("shutdown")
async def on_shutdown():
    shutdown_scheduler()

@app.get("/health")
async def health():
    return {"ok": True}
