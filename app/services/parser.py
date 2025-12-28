from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from bs4 import BeautifulSoup
from markdownify import markdownify as mdify

import trafilatura
from readability import Document

H1_RE = re.compile(r"^#\s+.*\n+", re.MULTILINE)

@dataclass
class ParsedContent:
    title: str
    image_url: Optional[str]
    body_markdown: str
    word_count: int

def _strip_leading_h1(markdown: str) -> str:
    # Remove a leading H1 if extractor already included it
    s = markdown.lstrip()
    if s.startswith("# "):
        # remove first line
        lines = s.splitlines()
        return "\n".join(lines[1:]).lstrip()
    return markdown.strip()

def _word_count(markdown: str) -> int:
    # rough but fine
    words = re.findall(r"\b\w+\b", markdown)
    return len(words)

def _extract_og_fields(html: str) -> tuple[Optional[str], Optional[str]]:
    soup = BeautifulSoup(html, "lxml")
    og_title = None
    og_image = None
    t = soup.find("meta", attrs={"property": "og:title"})
    if t and t.get("content"):
        og_title = t["content"].strip()
    i = soup.find("meta", attrs={"property": "og:image"})
    if i and i.get("content"):
        og_image = i["content"].strip()
    return og_title, og_image

def extract_markdown_from_html(html: str) -> str | None:
    # Prefer trafilatura markdown output
    md = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
        include_images=False,
        favor_precision=True,
        favor_recall=False,
    )
    if md and md.strip():
        return md.strip()

    # Fallback: readability -> markdownify
    try:
        doc = Document(html)
        main_html = doc.summary(html_partial=True)
        if main_html and main_html.strip():
            return mdify(main_html, heading_style="ATX").strip()
    except Exception:
        return None

    return None

def parse_article(
    source_url: str,
    rss_title: Optional[str],
    rss_image_url: Optional[str],
    encoded_html: Optional[str],
    page_html: Optional[str],
    force_h1_title: bool = True,
) -> ParsedContent | None:
    # Decide extraction source
    html_to_use = None
    og_title = None
    og_image = None

    if encoded_html and len(encoded_html) > 500:
        html_to_use = encoded_html
    elif page_html and len(page_html) > 500:
        html_to_use = page_html
        og_title, og_image = _extract_og_fields(page_html)

    if not html_to_use:
        return None

    md = extract_markdown_from_html(html_to_use)
    if not md:
        return None

    md = _strip_leading_h1(md)

    title = (rss_title or og_title or "").strip()
    if not title:
        # Try HTML <title>
        if page_html:
            soup = BeautifulSoup(page_html, "lxml")
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
    if not title:
        title = "Untitled"

    # Image choice: RSS -> OG -> none
    image_url = (rss_image_url or og_image)
    if image_url:
        image_url = image_url.strip() or None

    # Enforce title as H1
    if force_h1_title:
        md = f"# {title}\n\n{md.strip()}"

    # Always append source footer
    md = f"{md.strip()}\n\n---\n\nSource: {source_url}\n"

    wc = _word_count(md)

    return ParsedContent(
        title=title,
        image_url=image_url,
        body_markdown=md,
        word_count=wc,
    )
