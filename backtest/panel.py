"""Score every company at every formation date, using only what was public on that date.

One row per (company, June 30 of year Y): the latest 10-K visible that day, the same
build_facts + scorecard code the memos use, and a market cap from the cover-page share
count times the price actually quoted that day. The red-team penalty is zero here: this
tests the code-computed rubric alone, with no model in the loop.
"""
from __future__ import annotations

import json
import math
import random
import sys
import zipfile
from datetime import date

from ddagent.evidence import METRICS, EvidencePack, build_facts
from ddagent.pit import as_of, latest_10k_filed, shares_outstanding
from ddagent.prices import Prices
from ddagent.scorecard import metrics, score

KEEP_TAGS = {t for _, _, tags, _, _ in METRICS for t in tags}
MIN_REVENUE = 50e6
MAX_STALENESS_DAYS = 460  # latest 10-K must be at most ~15 months old at formation


def slim(cf: dict) -> dict:
    """Only the tags the rubric reads (companyfacts files are large)."""
    gaap = cf.get("facts", {}).get("us-gaap", {})
    dei = cf.get("facts", {}).get("dei", {})
    return {"cik": cf.get("cik"), "entityName": cf.get("entityName"), "facts": {
        "us-gaap": {k: v for k, v in gaap.items() if k in KEEP_TAGS},
        "dei": {k: v for k, v in dei.items() if k == "EntityCommonStockSharesOutstanding"}}}


def row_for(cf: dict, when: str, ticker: str | None, prices: Prices | None) -> dict | None:
    filed = latest_10k_filed(cf, when)
    if not filed or (date.fromisoformat(when) - date.fromisoformat(filed)).days > MAX_STALENESS_DAYS:
        return None
    view = as_of(cf, when)
    pack = EvidencePack(cf.get("entityName", ""), ticker or "", "")
    pack.facts = build_facts(view)
    latest = {}
    for f in pack.facts:
        if f.label not in latest or f.period >= latest[f.label].period:
            latest[f.label] = f
    rev = latest.get("Revenue")
    if not rev or rev.value < MIN_REVENUE:
        return None
    if (date.fromisoformat(when) - date.fromisoformat(rev.period)).days > MAX_STALENESS_DAYS + 90:
        return None

    mcap = price = None
    if ticker and prices:
        series = prices.monthly(ticker)
        sh = shares_outstanding(view)
        i = series.index_at(when) if series else None
        # The price must be from formation month itself, not a stale earlier bar.
        if series and sh and i is not None and series.months[i][:7] == when[:7]:
            price = series.raw_price(i)
            # The cover-page count can predate a split that happened before formation
            # (NVDA's 10-for-1 in June 2024): restate it in post-split shares.
            factor = 1.0
            for d, f in series.splits:
                if sh[1] < d <= when:
                    factor *= f
            mcap = sh[0] * factor * price
            pack.add_valuation(mcap, when, "shares outstanding x price")

    sc = score(pack, [])
    m = metrics(pack)
    row = {"cik": cf.get("cik"), "ticker": ticker or "", "name": cf.get("entityName", ""), "formed": when,
           "filed": filed, "fy_end": rev.period, "revenue": rev.value, "mcap": mcap, "price": price,
           "abs_points": sc.points, "abs_possible": sc.possible, "abs_pct": round(sc.pct, 4), "abs_verdict": sc.verdict}
    for ln in sc.lines:
        row[f"s_{ln.dimension.lower().replace(' ', '_')}"] = ln.score
    for k, v in m.items():
        row[f"m_{k}"] = v if math.isfinite(v) else (1e18 if v > 0 else -1e18)
    return row


def build(zip_path, listed: dict[int, dict], years: range, prices: Prices, delisted_sample: int = 3000,
          seed: int = 7, limit: int | None = None) -> list[dict]:
    rows: list[dict] = []
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.startswith("CIK") and n.endswith(".json")]
        ciks = {int(n[3:13]): n for n in names}
        listed_names = [ciks[c] for c in listed if c in ciks][:limit]
        others = sorted(n for c, n in ciks.items() if c not in listed)
        random.Random(seed).shuffle(others)
        n_other = delisted_sample if limit is None else min(delisted_sample, limit)
        todo = [(n, True) for n in listed_names] + [(n, False) for n in others[:n_other]]
        for i, (name, is_listed) in enumerate(todo, 1):
            try:
                cf = slim(json.loads(z.read(name)))
            except (json.JSONDecodeError, KeyError):
                continue
            cik = int(name[3:13])
            ticker = listed[cik]["ticker"] if is_listed else None
            for y in years:
                r = row_for(cf, f"{y}-06-30", ticker, prices if is_listed else None)
                if r:
                    r["cik"] = cik  # from the file name: a few companyfacts files have no "cik" field
                    r["listed_today"] = is_listed
                    rows.append(r)
            if i % 250 == 0 or i == len(todo):
                print(f"\r  scored {i}/{len(todo)} companies, {len(rows)} rows", end="", file=sys.stderr)
    print(file=sys.stderr)
    return rows
