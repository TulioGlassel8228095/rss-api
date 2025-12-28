from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any
import httpx
import feedparser

@dataclass
class RssFetchResult:
    parsed: Any
    etag: Optional[str]
    last_modified: Optional[str]
    not_modified: bool

class Fetcher:
    def __init__(self, user_agent: str, timeout_s: int):
        self._headers = {"User-Agent": user_agent}
        self._timeout = httpx.Timeout(timeout_s)

    async def fetch_rss(self, url: str, etag: str | None, last_modified: str | None) -> RssFetchResult:
        headers = dict(self._headers)
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        async with httpx.AsyncClient(headers=headers, timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 304:
                return RssFetchResult(parsed=None, etag=etag, last_modified=last_modified, not_modified=True)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            new_etag = resp.headers.get("ETag") or etag
            new_lm = resp.headers.get("Last-Modified") or last_modified
            return RssFetchResult(parsed=parsed, etag=new_etag, last_modified=new_lm, not_modified=False)

    async def fetch_page_html(self, url: str) -> tuple[Optional[str], Optional[str], int]:
        async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            status = resp.status_code
            ctype = resp.headers.get("Content-Type", "")
            if status >= 400:
                return None, ctype, status
            # Only accept HTML-ish
            text = resp.text
            return text, ctype, status
