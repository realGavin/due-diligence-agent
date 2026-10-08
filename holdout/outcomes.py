"""What happened to the business after each filing, from the company's later 10-Qs.

For the first two fiscal quarters after the fiscal year in the filing, each compared with
the same quarter a year earlier:

  growth_change   post-filing revenue growth minus the growth in the filed year (points).
                  Negative = growth slowed.
  margin_change   operating margin in those two quarters minus the same two quarters a
                  year earlier (points). Negative = margins shrank.
  deteriorated    margin_change <= -3 points, or growth_change <= -10 points.

These are the primary outcomes in PREREGISTRATION.md: they measure what a diligence memo
claims to judge (the business), with far less noise than a stock price.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from ddagent.edgar import FACTS_URL, Edgar
from ddagent.evidence import METRICS

SNAPSHOT_CACHE = Path(".cache/holdout/facts_now")
REVENUE_TAGS = next(tags for key, _, tags, _, _ in METRICS if key == "revenue")
OPINC_TAGS = ("OperatingIncomeLoss",)
MARGIN_DROP, GROWTH_DROP = -3.0, -10.0  # deterioration thresholds, in points


def quarterly(cf: dict, tags: tuple[str, ...]) -> dict[str, float]:
    """end date -> value for three-month periods (80-100 days) from 10-Qs and 10-Ks. Within a
    tag the latest filing wins (restatements); across tags the first tag listed wins."""
    gaap = cf.get("facts", {}).get("us-gaap", {})
    out: dict[str, float] = {}
    for tag in tags:
        best: dict[str, tuple[str, float]] = {}
        for r in gaap.get(tag, {}).get("units", {}).get("USD", []):
            if "start" not in r or not str(r.get("form", "")).startswith(("10-Q", "10-K")):
                continue
            days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
            if 80 <= days <= 100 and (r["end"] not in best or r.get("filed", "") > best[r["end"]][0]):
                best[r["end"]] = (r.get("filed", ""), float(r["val"]))
        for e, (_, v) in best.items():
            out.setdefault(e, v)
    return out


def _year_ago(q: dict[str, float], end: str) -> str | None:
    d = date.fromisoformat(end)
    for e in q:
        if 355 <= (d - date.fromisoformat(e)).days <= 375:
            return e
    return None


def measure(cf_now: dict, fy_end: str, filed_growth: float | None, quarters: int = 2) -> dict | None:
    """Outcomes for the first `quarters` fiscal quarters ending after fy_end; None if not yet reported."""
    rev = quarterly(cf_now, REVENUE_TAGS)
    oi = quarterly(cf_now, OPINC_TAGS)
    post = sorted(e for e in rev if e > fy_end)[:quarters]
    if len(post) < quarters:
        return None
    prior = [_year_ago(rev, e) for e in post]
    if any(p is None for p in prior):
        return None
    r_now, r_then = sum(rev[e] for e in post), sum(rev[p] for p in prior)
    if r_then <= 0 or r_now <= 0:
        return None
    out = {"quarters": post, "post_growth": (r_now / r_then - 1) * 100}
    if filed_growth is not None:
        out["growth_change"] = out["post_growth"] - filed_growth
    if all(e in oi for e in post) and all(p in oi for p in prior):
        out["margin_change"] = (sum(oi[e] for e in post) / r_now - sum(oi[p] for p in prior) / r_then) * 100
    if "growth_change" in out or "margin_change" in out:
        out["deteriorated"] = (out.get("margin_change", 0.0) <= MARGIN_DROP or
                               out.get("growth_change", 0.0) <= GROWTH_DROP)
    return out


def realized_direction(o: dict) -> dict:
    """Map outcomes to the forecast vocabulary (same bands the prompts state)."""
    d = {}
    if "growth_change" in o:
        g = o["growth_change"]
        d["revenue_growth"] = "accelerate" if g > 2 else "decelerate" if g < -2 else "stable"
    if "margin_change" in o:
        m = o["margin_change"]
        d["operating_margin"] = "expand" if m > 1 else "compress" if m < -1 else "stable"
    return d


def fetch_now(edgar: Edgar, cik: int) -> dict:
    return edgar._json(FACTS_URL.format(cik=cik))


def pack_baseline(pack) -> tuple[str | None, float | None]:
    """(fiscal year end, revenue growth) of the year in the filing, from its evidence pack."""
    latest = {}
    for f in pack.facts:
        if f.label not in latest or f.period >= latest[f.label].period:
            latest[f.label] = f
    rev, g = latest.get("Revenue"), latest.get("Revenue growth (YoY)")
    return (rev.period if rev else None), (g.value if g else None)


def attach(rows: list[dict], edgar: Edgar) -> list[dict]:
    """Add fundamental outcomes to each run row, from a fresh companyfacts snapshot."""
    from .sample import load_pack

    out = []
    for r in rows:
        meta, pack = load_pack(r["ticker"])
        fy_end, growth = pack_baseline(pack)
        if not fy_end:
            continue
        o = measure(fetch_now(edgar, int(meta["cik"])), fy_end, growth)
        if o:
            out.append({**r, "fund": o, "realized": realized_direction(o)})
    return out
