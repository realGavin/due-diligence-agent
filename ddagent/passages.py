"""Recover the full passage behind a web citation.

The search API returns each citation's cited_text truncated to roughly 150 characters,
so a claim that quotes the rest of the sentence ("...while Meta accounted for 16%") can't
be checked against it. Here we fetch the page ourselves, find where the cited text
starts, and keep a window around it. The gate then checks claims against what the page
actually says. If the page can't be fetched or the passage can't be found, we keep the
truncated text, which only makes the gate stricter.
"""
from __future__ import annotations

import hashlib
import html
import os
import re
from pathlib import Path

import httpx

from .filing import html_to_text

CACHE = Path(".cache/web")
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def clean_cited(cited: str) -> str:
    return _norm(cited).removesuffix("...").removesuffix("…").strip()


def _page_text(url: str) -> str | None:
    if os.environ.get("DD_NO_FETCH"):  # tests run offline
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / hashlib.sha256(url.encode()).hexdigest()[:24]
    if key.exists():
        return key.read_text()
    ua = os.environ.get("SEC_USER_AGENT") if "sec.gov" in url else BROWSER_UA
    try:
        r = httpx.get(url, headers={"User-Agent": ua or BROWSER_UA}, timeout=20, follow_redirects=True)
        r.raise_for_status()
    except Exception:
        return None
    ctype = r.headers.get("content-type", "")
    if "html" not in ctype and "text" not in ctype:
        return None
    text = _norm(html_to_text(r.text))
    key.write_text(text)
    return text


def expand(url: str, cited: str, before: int = 150, after: int = 700) -> str:
    """The cited text plus the page passage around it (or just the cited text if the page
    can't be fetched or the passage can't be found).

    Both are kept on purpose: the cited text is what the search index held when the model
    read it, and a live page can have moved on since (a market-cap page updates every
    day). A claim passes if its numbers are in either; nothing outside the page is added."""
    short = clean_cited(cited)
    page = _page_text(url)
    if not page or len(short) < 25:
        return short
    probe = short[:60].lower()
    i = page.lower().find(probe)
    if i < 0:
        return short
    return f"{short} […] {page[max(0, i - before): i + len(short) + after]}"
