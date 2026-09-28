"""Download everything the backtest needs. Free, public sources only; all cached in .cache/backtest.

  SEC companyfacts.zip       every XBRL value every company has filed, with its filing date
  SEC company_tickers_exchange  today's listed tickers (CIK -> ticker, exchange)
  SEC submissions/CIK*.json  industry code (SIC) per company
  Ken French data library    Fama-French 5 factors + momentum, monthly
  Yahoo Finance chart API    monthly prices (split-adjusted and total-return)
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import httpx

from ddagent.edgar import Edgar
from ddagent.prices import Prices

CACHE = Path(".cache/backtest")
FACTS_ZIP = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
TICKERS_EX = "https://www.sec.gov/files/company_tickers_exchange.json"
FF5 = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip"
MOM = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip"
EXCHANGES = {"NYSE", "Nasdaq", "NYSE American", "NYSE MKT", "NYSE Arca", "CBOE", "Cboe"}


def _ua() -> str:
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise RuntimeError('Set SEC_USER_AGENT="Your Name you@example.com" (SEC requires it).')
    return ua


def download(url: str, dest: Path, headers: dict | None = None) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"downloading {url}", file=sys.stderr)
    with httpx.stream("GET", url, headers=headers or {}, timeout=None, follow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(tmp, "wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done / 1e6:,.0f} / {total / 1e6:,.0f} MB", end="", file=sys.stderr)
    print(file=sys.stderr)
    tmp.rename(dest)
    return dest


def companyfacts_zip() -> Path:
    return download(FACTS_ZIP, CACHE / "companyfacts.zip", {"User-Agent": _ua()})


def listed_tickers() -> dict[int, dict]:
    """CIK -> {ticker, name, exchange} for companies listed on a US exchange today."""
    path = download(TICKERS_EX, CACHE / "company_tickers_exchange.json", {"User-Agent": _ua()})
    raw = json.loads(path.read_text())
    cols = raw["fields"]
    out: dict[int, dict] = {}
    for row in raw["data"]:
        r = dict(zip(cols, row))
        if r.get("exchange") in EXCHANGES and r.get("ticker") and int(r["cik"]) not in out:
            out[int(r["cik"])] = {"ticker": r["ticker"], "name": r["name"], "exchange": r["exchange"]}
    return out


def sic_codes(ciks: list[int]) -> dict[int, int]:
    """SIC industry code per CIK from each company's submissions record (cached)."""
    path = CACHE / "sic.json"
    known: dict[str, int] = json.loads(path.read_text()) if path.exists() else {}
    edgar = Edgar(_ua(), cache_dir=CACHE / "edgar")
    todo = [c for c in ciks if str(c) not in known]
    for i, cik in enumerate(todo, 1):
        try:
            sub = edgar._json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
            known[str(cik)] = int(sub.get("sic") or 0)
        except httpx.HTTPError:
            known[str(cik)] = 0
        if i % 200 == 0 or i == len(todo):
            print(f"\r  SIC codes {i}/{len(todo)}", end="", file=sys.stderr)
            path.write_text(json.dumps(known))
    if todo:
        print(file=sys.stderr)
    return {int(k): v for k, v in known.items()}


def _french(url: str, name: str) -> dict[str, dict[str, float]]:
    """Monthly rows of a Ken French CSV as {YYYY-MM: {factor: decimal return}}."""
    path = download(url, CACHE / name)
    with zipfile.ZipFile(path) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")
    out: dict[str, dict[str, float]] = {}
    header = None
    for row in csv.reader(io.StringIO(text)):
        row = [c.strip() for c in row]
        if not any(row):
            if out:  # the monthly block ends at the first blank line after data
                break
            continue
        if row[0] == "" and len(row) > 1:
            if not out:
                header = row[1:]
            continue
        if len(row[0]) == 6 and row[0].isdigit() and header:
            ym = f"{row[0][:4]}-{row[0][4:]}"
            out[ym] = {h: float(v) / 100 for h, v in zip(header, row[1:]) if v}
        elif out:
            break  # annual block follows
    return out


def factors() -> dict[str, dict[str, float]]:
    ff = _french(FF5, "ff5.zip")
    mom = _french(MOM, "mom.zip")
    for ym, row in ff.items():
        if ym in mom:
            row["Mom"] = next(iter(mom[ym].values()))
    return {ym: r for ym, r in ff.items() if "Mom" in r}


def fetch_prices(tickers: list[str]) -> Prices:
    p = Prices(CACHE / "prices")
    for i, t in enumerate(sorted(set(tickers)), 1):
        p.monthly(t, start="2010-01-01")
        if i % 50 == 0 or i == len(tickers):
            print(f"\r  prices {i}/{len(tickers)}", end="", file=sys.stderr)
    print(file=sys.stderr)
    return p
