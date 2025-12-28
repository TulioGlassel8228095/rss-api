from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

def _sqlite_url(path: str) -> str:
    # Ensure absolute path works inside container volume, sqlite is file-based
    return f"sqlite+aiosqlite:///{path}"

engine = create_async_engine(
    _sqlite_url(settings.db_path),
    echo=False,
    future=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
