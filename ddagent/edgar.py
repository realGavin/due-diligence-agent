"""Thin, cached client for SEC EDGAR's free public APIs.

SEC asks every client to send a descriptive User-Agent with contact info and to stay
under 10 requests/second. Set SEC_USER_AGENT="Your Name you@example.com".
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"


@dataclass(frozen=True)
class Company:
    cik: int
    ticker: str
    name: str


@dataclass(frozen=True)
class Filing:
    form: str
    accession: str
    filed: str
    period: str
    url: str


class Edgar:
    def __init__(self, user_agent: str | None = None, cache_dir: str | Path = ".cache/edgar"):
        ua = user_agent or os.environ.get("SEC_USER_AGENT")
        if not ua:
            raise RuntimeError('Set SEC_USER_AGENT="Your Name you@example.com" (SEC requires it).')
        self._http = httpx.Client(headers={"User-Agent": ua}, timeout=30, follow_redirects=True)
        self._cache = Path(cache_dir)
        self._cache.mkdir(parents=True, exist_ok=True)
        self._last = 0.0

    # -- transport -------------------------------------------------------------
    def _get(self, url: str) -> bytes:
        key = self._cache / hashlib.sha256(url.encode()).hexdigest()[:24]
        if key.exists():
            return key.read_bytes()
        wait = 0.12 - (time.monotonic() - self._last)  # stay well under 10 req/s
        if wait > 0:
            time.sleep(wait)
        resp = self._http.get(url)
        self._last = time.monotonic()
        resp.raise_for_status()
        key.write_bytes(resp.content)
        return resp.content

    def _json(self, url: str) -> dict:
        return json.loads(self._get(url))

    # -- API -------------------------------------------------------------------
    def company(self, ticker: str) -> Company:
        t = ticker.upper().replace(".", "-")
        for row in self._json(TICKERS_URL).values():
            if row["ticker"].upper() == t:
                return Company(int(row["cik_str"]), row["ticker"], row["title"])
        raise LookupError(f"Ticker {ticker!r} not found in SEC company list")

    def latest_filing(self, cik: int, form: str = "10-K") -> Filing:
        recent = self._json(SUBMISSIONS_URL.format(cik=cik))["filings"]["recent"]
        for i, f in enumerate(recent["form"]):
            if f == form:
                acc = recent["accessionNumber"][i]
                return Filing(
                    form=f,
                    accession=acc,
                    filed=recent["filingDate"][i],
                    period=recent["reportDate"][i],
                    url=ARCHIVE_URL.format(cik=cik, acc=acc.replace("-", ""), doc=recent["primaryDocument"][i]),
                )
        raise LookupError(f"No {form} found for CIK {cik}")

    def filing_html(self, filing: Filing) -> str:
        return self._get(filing.url).decode("utf-8", errors="replace")

    def company_facts(self, cik: int) -> dict:
        return self._json(FACTS_URL.format(cik=cik))
