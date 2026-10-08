"""Monthly prices from Yahoo Finance's public chart endpoint (no API key), cached on disk.

Two series matter and they are not interchangeable:
  close     split-adjusted price. Times the split factor it gives the price actually
            quoted that day, which is what shares outstanding (as reported) multiply against.
  adjclose  split- and dividend-adjusted. Its month-over-month change is the total return.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


@dataclass
class Series:
    ticker: str
    months: list[str]  # month-end dates, ISO, ascending
    close: list[float]  # split-adjusted
    adjclose: list[float]  # split + dividend adjusted
    splits: list[tuple[str, float]]  # (date, factor): 2-for-1 is 2.0

    def index_at(self, d: str) -> int | None:
        """Last month on or before d."""
        idx = None
        for i, m in enumerate(self.months):
            if m <= d:
                idx = i
            else:
                break
        return idx

    def raw_price(self, i: int) -> float:
        """Price as quoted at months[i]: undo splits that happened after it."""
        factor = 1.0
        for d, f in self.splits:
            if d > self.months[i]:
                factor *= f
        return self.close[i] * factor


def _month_end(ts: int) -> str:
    d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
    # Yahoo stamps monthly bars at the first of the month; the bar's close is that month's last close.
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1).isoformat()


def parse_chart(ticker: str, payload: dict) -> Series | None:
    res = (payload.get("chart") or {}).get("result") or []
    if not res:
        return None
    r = res[0]
    ts = r.get("timestamp") or []
    q = (r.get("indicators", {}).get("quote") or [{}])[0]
    adj = (r.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or []
    close = q.get("close") or []
    months, c, a = [], [], []
    for t, cl, ad in zip(ts, close, adj):
        if cl is None or ad is None:
            continue
        m = _month_end(t)
        if months and months[-1] == m:  # Yahoo sometimes adds a partial "current" bar
            c[-1], a[-1] = cl, ad
            continue
        months.append(m)
        c.append(float(cl))
        a.append(float(ad))
    splits = []
    for ev in (r.get("events") or {}).get("splits", {}).values():
        num, den = ev.get("numerator"), ev.get("denominator")
        if num and den:
            d = datetime.fromtimestamp(ev["date"], tz=timezone.utc).date().isoformat()
            splits.append((d, float(num) / float(den)))
    splits.sort()
    return Series(ticker, months, c, a, splits) if months else None


def _client():
    """Yahoo rejects clients that don't look like a browser at the TLS level (plain httpx gets
    HTTP 429 on every request). curl_cffi impersonates Chrome, as yfinance does; fall back
    to httpx if it isn't installed."""
    try:
        from curl_cffi import requests as creq

        return creq.Session(impersonate="chrome", timeout=30)
    except ImportError:
        return httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True)


class Prices:
    def __init__(self, cache_dir: str | Path = ".cache/prices", delay: float = 0.35):
        self._cache = Path(cache_dir)
        self._cache.mkdir(parents=True, exist_ok=True)
        self._http = _client()
        self._delay = delay
        self._last = 0.0

    def monthly(self, ticker: str, start: str = "2010-01-01", refresh: bool = False) -> Series | None:
        sym = ticker.upper().replace(".", "-")
        path = self._cache / f"{sym}.json"
        if path.exists() and not refresh:
            payload = json.loads(path.read_text())
        else:
            p1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
            p2 = int(time.time())
            params = {"period1": p1, "period2": p2, "interval": "1mo", "events": "split,div", "includeAdjustedClose": "true"}
            payload, status = None, None
            for attempt in range(5):
                wait = self._delay - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
                resp = self._http.get(CHART_URL.format(sym=sym), params=params)
                self._last = time.monotonic()
                status = resp.status_code
                if resp.status_code == 404:
                    payload = {"chart": {"result": None}}
                    break
                if resp.status_code == 429 or resp.status_code >= 500:
                    time.sleep(5 * 2 ** attempt)
                    continue
                resp.raise_for_status()
                payload = resp.json()
                break
            if payload is None:
                raise RuntimeError(f"Yahoo kept refusing {sym} (HTTP {status}); rerun later (progress is cached)")
            path.write_text(json.dumps(payload))
        return parse_chart(sym, payload)
