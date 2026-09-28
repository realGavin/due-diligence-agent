"""Point-in-time views of SEC company facts.

Every XBRL value in companyfacts carries the date of the filing it appeared in
("filed"). Dropping every row filed after a date gives exactly what an investor could
have read on that date: later restatements, and 10-Ks not yet filed, disappear. The live
scorecard code then runs on that view unchanged, so the backtest tests the same
rubric the memos use.
"""
from __future__ import annotations


def as_of(companyfacts: dict, when: str) -> dict:
    """A copy of companyfacts containing only rows filed on or before `when` (ISO date)."""
    out = {k: v for k, v in companyfacts.items() if k != "facts"}
    facts: dict = {}
    for taxonomy, tags in companyfacts.get("facts", {}).items():
        kept_tags = {}
        for tag, body in tags.items():
            units = {}
            for unit, rows in body.get("units", {}).items():
                keep = [r for r in rows if r.get("filed", "9999") <= when]
                if keep:
                    units[unit] = keep
            if units:
                kept_tags[tag] = {**{k: v for k, v in body.items() if k != "units"}, "units": units}
        if kept_tags:
            facts[taxonomy] = kept_tags
    out["facts"] = facts
    return out


def latest_10k_filed(companyfacts: dict, when: str | None = None) -> str | None:
    """Filing date of the most recent 10-K visible in the facts (optionally as of `when`)."""
    best = None
    for tags in companyfacts.get("facts", {}).values():
        for body in tags.values():
            for rows in body.get("units", {}).values():
                for r in rows:
                    f = r.get("filed")
                    if f and str(r.get("form", "")).startswith("10-K") and (when is None or f <= when):
                        if best is None or f > best:
                            best = f
    return best


def shares_outstanding(companyfacts: dict) -> tuple[float, str] | None:
    """Latest cover-page share count (dei:EntityCommonStockSharesOutstanding), summed across
    share classes reported for the same date. Returns (shares, as-of date)."""
    rows = companyfacts.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding", {}) \
        .get("units", {}).get("shares", [])
    if not rows:
        return None
    last_filed = max(r.get("filed", "") for r in rows)
    latest = [r for r in rows if r.get("filed", "") == last_filed]
    end = max(r["end"] for r in latest)
    # Multiple classes (e.g. Class A and B) appear as separate rows with the same end date.
    vals = {(r.get("accn"), r["val"]) for r in latest if r["end"] == end}
    total = sum(v for _, v in vals)
    return (float(total), end) if total > 0 else None
