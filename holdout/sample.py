"""Build the holdout sample: every US-listed non-financial company worth >= $300M that filed
a 10-K inside the window, with an evidence pack built only from what was public at filing.

Valuation uses the price at the last month-end BEFORE the filing (known on filing day),
times the cover-page share count, restated for any split in between. Returns are measured
later, from the first month-end on or after the filing.
"""
from __future__ import annotations

import json
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path

from backtest import data
from backtest.analyze import is_financial
from backtest.panel import slim
from ddagent.edgar import ARCHIVE_URL, SUBMISSIONS_URL, Edgar, Filing
from ddagent.evidence import EvidencePack, build_facts
from ddagent.filing import build_excerpts
from ddagent.pit import as_of, shares_outstanding
from ddagent.prices import Prices

CACHE = Path(".cache/holdout")
PACKS = CACHE / "packs"
# After Sonnet 4.5's July 2025 training cutoff. Filings through March 2026 have six months of
# returns by the end of September 2026; August-September 2025 filings have twelve.
WINDOW = ("2025-08-01", "2026-03-31")
MIN_MCAP = 300e6
TWELVE_MONTH_CUTOFF = "2025-09-30"


def tenk_in_window(cf: dict, start: str, end: str) -> tuple[str, str] | None:
    """(filed, accession) of the first 10-K filed inside [start, end], from the facts themselves."""
    hits = set()
    for tags in cf.get("facts", {}).values():
        for body in tags.values():
            for rows in body.get("units", {}).values():
                for r in rows:
                    if r.get("form") == "10-K" and start <= r.get("filed", "") <= end and r.get("accn"):
                        hits.add((r["filed"], r["accn"]))
    return min(hits) if hits else None


def market_cap_before(view: dict, series, filed: str) -> tuple[float, float, str] | None:
    """(market cap, price, month-end) using the last month-end strictly before the filing."""
    sh = shares_outstanding(view)
    if not series or not sh:
        return None
    i = None
    for k, m in enumerate(series.months):
        if m < filed:
            i = k
    if i is None:
        return None
    month = series.months[i]
    price = series.raw_price(i)
    factor = 1.0
    for d, f in series.splits:
        if sh[1] < d <= month:
            factor *= f
    return sh[0] * factor * price, price, month


def filing_for(edgar: Edgar, cik: int, accn: str) -> Filing | None:
    recent = edgar._json(SUBMISSIONS_URL.format(cik=cik))["filings"]["recent"]
    for i, a in enumerate(recent["accessionNumber"]):
        if a == accn:
            return Filing(recent["form"][i], a, recent["filingDate"][i], recent["reportDate"][i],
                          ARCHIVE_URL.format(cik=cik, acc=a.replace("-", ""), doc=recent["primaryDocument"][i]))
    return None


def build_pack(cf: dict, ticker: str, filed: str, filing_html: str, filing_url: str, mcap: float, month: str) -> EvidencePack:
    view = as_of(cf, filed)
    pack = EvidencePack(cf.get("entityName", ticker), ticker, filing_url)
    pack.facts = build_facts(view)
    pack.excerpts = build_excerpts(filing_html)
    pack.add_valuation(mcap, month, "code: cover-page shares x price at the month-end before filing")
    return pack


def prepare(limit: int | None = None, sample_size: int | None = None, seed: int = 2025,
            window: tuple[str, str] = WINDOW) -> list[dict]:
    """Scan every listed company for a 10-K in the window. With `sample_size`, draw a random
    sample (fixed seed) before downloading filings, so the sample is chosen blind to anything
    but eligibility."""
    PACKS.mkdir(parents=True, exist_ok=True)
    listed = data.listed_tickers()
    zpath = data.companyfacts_zip()
    prices = Prices(data.CACHE / "prices")
    edgar = Edgar(data._ua(), cache_dir=data.CACHE / "edgar")
    start, end = window

    candidates = []
    with zipfile.ZipFile(zpath) as z:
        names = {int(n[3:13]): n for n in z.namelist() if n.startswith("CIK") and n.endswith(".json")}
        for i, (cik, info) in enumerate(listed.items(), 1):
            if cik not in names:
                continue
            cf = slim(json.loads(z.read(names[cik])))
            hit = tenk_in_window(cf, start, end)
            if hit:
                candidates.append((cik, info["ticker"], hit[0], hit[1], cf))
            if i % 500 == 0:
                print(f"\r  scanned {i}/{len(listed)} listed companies, {len(candidates)} filed in window",
                      end="", file=sys.stderr)
    print(file=sys.stderr)

    sic = data.sic_codes([c[0] for c in candidates])
    import random

    # Every August-September 2025 filer is kept (the only group with twelve months of returns);
    # the rest are drawn at random with a fixed seed.
    candidates.sort(key=lambda c: c[0])
    random.Random(seed).shuffle(candidates)
    candidates.sort(key=lambda c: c[2] > TWELVE_MONTH_CUTOFF)
    target = sample_size or limit
    manifest = []
    for k, (cik, ticker, filed, accn, cf) in enumerate(candidates, 1):
        if is_financial(sic.get(cik, 0)):
            continue
        out = PACKS / f"{ticker}.json"
        if out.exists():
            manifest.append(json.loads(out.read_text())["meta"])
            if target and len(manifest) >= target:
                break
            continue
        view = as_of(cf, filed)
        mc = market_cap_before(view, prices.monthly(ticker), filed)
        if not mc or mc[0] < MIN_MCAP:
            continue
        f = filing_for(edgar, cik, accn)
        if not f:
            continue
        try:
            html = edgar.filing_html(f)
        except Exception as e:  # noqa: BLE001 - a missing document skips one company, not the run
            print(f"  skip {ticker}: {e}", file=sys.stderr)
            continue
        pack = build_pack(cf, ticker, filed, html, f.url, mc[0], mc[2])
        if len(pack.excerpts) < 3:  # filing text didn't parse into sections
            continue
        meta = {"ticker": ticker, "cik": cik, "filed": filed, "accession": accn, "sic": sic.get(cik, 0),
                "mcap": mc[0], "price": mc[1], "valuation_month": mc[2], "url": f.url}
        out.write_text(json.dumps({"meta": meta, "pack": asdict(pack)}))
        manifest.append(meta)
        print(f"\r  packs built {len(manifest)} ({k}/{len(candidates)} checked)", end="", file=sys.stderr)
        if target and len(manifest) >= target:
            break
    print(file=sys.stderr)
    (CACHE / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def load_pack(ticker: str) -> tuple[dict, EvidencePack]:
    from ddagent.evidence import Excerpt, Fact

    raw = json.loads((PACKS / f"{ticker}.json").read_text())
    p = raw["pack"]
    pack = EvidencePack(p["company"], p["ticker"], p["filing_url"])
    pack.facts = [Fact(**f) for f in p["facts"]]
    pack.excerpts = [Excerpt(**e) for e in p["excerpts"]]
    return raw["meta"], pack
