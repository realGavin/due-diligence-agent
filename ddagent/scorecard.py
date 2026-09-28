"""The verdict comes from a fixed rubric computed in code, not from the model's opinion.

Each available dimension scores 0-2 from facts in the evidence pack. High-severity red-team
objections subtract. The verdict follows from the share of available points:
    >= 65%  Dig deeper   ·   40-65%  Watch   ·   < 40%  Pass
Missing dimensions (a bank has no gross margin; no market cap was found) are left out
of the denominator instead of counting as zero.

The absolute thresholds are the same for every industry, which is unfair to some (a
retailer's 4% operating margin fails a test built for software). `score_relative` scores
the same dimensions against the company's industry peers instead, using percentile
tables the backtest writes (backtest/peers.json). Both appear in the memo.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

from .agents import Claim
from .evidence import EvidencePack, Fact

THRESHOLDS = (0.65, 0.40)


@dataclass
class Line:
    dimension: str
    score: int | None  # None = not scorable (missing data)
    basis: str
    fact_ids: list[str]


@dataclass
class Scorecard:
    lines: list[Line]
    penalty: float
    penalty_basis: str
    points: float
    possible: int
    verdict: str

    @property
    def pct(self) -> float:
        return self.points / self.possible if self.possible else 0.0


def _latest(pack: EvidencePack) -> dict[str, Fact]:
    out: dict[str, Fact] = {}
    for f in pack.facts:
        if f.label not in out or f.period >= out[f.label].period:
            out[f.label] = f
    return out


def _tier(v: float, hi: float, mid: float) -> int:
    return 2 if v >= hi else 1 if v >= mid else 0


def score(pack: EvidencePack, objections: list[Claim]) -> Scorecard:
    L = _latest(pack)
    lines: list[Line] = []

    def get(*labels):
        return [L.get(x) for x in labels]

    g, = get("Revenue growth (YoY)")
    lines.append(Line("Growth", _tier(g.value, 15, 3) if g else None,
                      f"revenue {g.display()} YoY (2: >=15%, 1: >=3%)" if g else "no revenue history", [g.id] if g else []))

    om, roe = get("Operating margin", "Return on equity")
    if om or roe:
        s_om = _tier(om.value, 20, 8) if om else 0
        s_roe = _tier(roe.value, 20, 10) if roe and roe.value > 0 else 0
        best = max(s_om, s_roe)
        basis = ", ".join(x for x in (f"operating margin {om.display()}" if om else "",
                                      f"ROE {roe.display()}" if roe else "") if x)
        lines.append(Line("Profitability", best, basis + " (better of: margin 20/8%, ROE 20/10%)",
                          [x.id for x in (om, roe) if x]))
    else:
        lines.append(Line("Profitability", None, "no margin data", []))

    fcf, ni = get("Free cash flow", "Net income")
    if fcf and ni:
        if ni.value <= 0 or fcf.value <= 0:
            s, basis = (0 if fcf.value <= 0 else 1), f"FCF {fcf.display()} vs net income {ni.display()}"
        else:
            ratio = fcf.value / ni.value
            s, basis = _tier(ratio, 0.9, 0.5), f"FCF / net income = {ratio:.2f} (2: >=0.9, 1: >=0.5)"
        lines.append(Line("Cash conversion", s, basis, [fcf.id, ni.id]))
    else:
        lines.append(Line("Cash conversion", None, "missing FCF or net income", []))

    nd, = get("Net debt (LT debt - cash)")
    if nd and fcf:
        if nd.value <= 0:
            s, basis = 2, f"net cash ({nd.display()} net debt)"
        elif fcf.value > 0:
            yrs = nd.value / fcf.value
            s, basis = (1 if yrs <= 3 else 0), f"net debt = {yrs:.1f} years of FCF (1: <=3)"
        else:
            s, basis = 0, f"net debt {nd.display()} with negative FCF"
        lines.append(Line("Balance sheet", s, basis, [nd.id, fcf.id]))
    else:
        lines.append(Line("Balance sheet", None, "missing debt or FCF data", []))

    dil, = get("Diluted share count change (YoY)")
    lines.append(Line("Dilution", (2 if dil.value <= 0.5 else 1 if dil.value <= 3 else 0) if dil else None,
                      f"diluted shares {dil.display()} YoY (2: <=0.5%, 1: <=3%)" if dil else "no share data",
                      [dil.id] if dil else []))

    fy, mc = get("FCF yield", "Market cap")
    if fy:
        lines.append(Line("Valuation", _tier(fy.value, 5, 2.5), f"FCF yield {fy.display()} (2: >=5%, 1: >=2.5%)", [fy.id]))
    elif mc and fcf and fcf.value <= 0:
        lines.append(Line("Valuation", 0, f"market cap {mc.display()} with negative FCF: no cash yield",
                          [mc.id, fcf.id]))
    else:
        lines.append(Line("Valuation", None, "no market cap found, or FCF not positive", []))

    highs = sum(1 for o in objections if (o.severity or "").lower() == "high")
    penalty = min(0.5 * highs, 2.0)
    scored = [x for x in lines if x.score is not None]
    possible = 2 * len(scored)
    points = max(0.0, sum(x.score for x in scored) - penalty)
    pct = points / possible if possible else 0.0
    verdict = "Dig deeper" if pct >= THRESHOLDS[0] else "Watch" if pct >= THRESHOLDS[1] else "Pass"
    return Scorecard(lines, penalty, f"{highs} high-severity red-team objection(s) × 0.5, capped at 2",
                     points, possible, verdict)


# ----------------------------------------------------------------------------- relative

# Dimension -> (metric key, higher is better?)
RELATIVE_DIMS = {
    "Growth": [("growth", True)],
    "Profitability": [("op_margin", True), ("roe", True)],
    "Cash conversion": [("cash_conversion", True)],
    "Balance sheet": [("leverage_years", False)],
    "Dilution": [("dilution", False)],
    "Valuation": [("fcf_yield", True)],
}


def metrics(pack: EvidencePack) -> dict[str, float]:
    """Raw values behind each dimension, on a scale where comparing to peers makes sense.

    Cases the absolute rubric treats as automatic fails are mapped to +/-inf so they rank
    last among peers (negative FCF has no meaningful "leverage in years of FCF").
    """
    L = _latest(pack)
    v = lambda k: L[k].value if k in L else None  # noqa: E731
    out: dict[str, float] = {}
    if v("Revenue growth (YoY)") is not None:
        out["growth"] = v("Revenue growth (YoY)")
    if v("Operating margin") is not None:
        out["op_margin"] = v("Operating margin")
    if v("Return on equity") is not None and v("Return on equity") > 0:
        out["roe"] = v("Return on equity")  # negative equity makes ROE meaningless
    fcf, ni, nd = v("Free cash flow"), v("Net income"), v("Net debt (LT debt - cash)")
    if fcf is not None and ni is not None:
        out["cash_conversion"] = fcf / ni if (fcf > 0 and ni > 0) else (-math.inf if fcf <= 0 else math.inf)
    if nd is not None and fcf is not None:
        # Net cash ranks best, debt with negative FCF ranks worst, as in the absolute rubric.
        out["leverage_years"] = -math.inf if nd <= 0 else (nd / fcf if fcf > 0 else math.inf)
    if v("Diluted share count change (YoY)") is not None:
        out["dilution"] = v("Diluted share count change (YoY)")
    if v("FCF yield") is not None:
        out["fcf_yield"] = v("FCF yield")
    elif v("Market cap") is not None and fcf is not None and fcf <= 0:
        out["fcf_yield"] = -math.inf
    return out


def percentile(value: float, peers: list[float]) -> float:
    """Share of peers below `value` (ties count half). `peers` must be sorted."""
    if not peers:
        return 0.5
    lo, hi = bisect.bisect_left(peers, value), bisect.bisect_right(peers, value)
    return (lo + 0.5 * (hi - lo)) / len(peers)


def score_relative(m: dict[str, float], peers: dict[str, list[float]], group: str,
                   objections: list[Claim] | None = None, min_peers: int = 15) -> Scorecard:
    """Top third of the peer group = 2, middle third = 1, bottom third = 0, per dimension."""
    lines: list[Line] = []
    for dim, keys in RELATIVE_DIMS.items():
        best, parts = None, []
        for key, higher in keys:
            if key not in m or len(peers.get(key, [])) < min_peers:
                continue
            p = percentile(m[key], peers[key])
            p = p if higher else 1 - p
            s = 2 if p >= 2 / 3 else 1 if p >= 1 / 3 else 0
            parts.append(f"{key.replace('_', ' ')} at {p * 100:.0f}th pct")
            best = s if best is None else max(best, s)
        basis = (", ".join(parts) + f" of {group_label(group)} peers") if parts else "not enough peers or data"
        lines.append(Line(dim, best, basis, []))
    highs = sum(1 for o in (objections or []) if (o.severity or "").lower() == "high")
    penalty = min(0.5 * highs, 2.0)
    scored = [x for x in lines if x.score is not None]
    possible = 2 * len(scored)
    points = max(0.0, sum(x.score for x in scored) - penalty)
    pct = points / possible if possible else 0.0
    verdict = "Dig deeper" if pct >= THRESHOLDS[0] else "Watch" if pct >= THRESHOLDS[1] else "Pass"
    return Scorecard(lines, penalty, f"{highs} high-severity red-team objection(s) × 0.5, capped at 2",
                     points, possible, verdict)


# ----------------------------------------------------------------------------- peer groups

def division(sic: int) -> str:
    """SIC division: the fallback peer group when a 2-digit industry is too thin."""
    s = sic // 100
    for lo, hi, name in [(1, 9, "Agriculture"), (10, 14, "Mining"), (15, 17, "Construction"),
                         (20, 39, "Manufacturing"), (40, 49, "Transport & utilities"), (50, 51, "Wholesale"),
                         (52, 59, "Retail"), (60, 67, "Finance"), (70, 89, "Services"), (90, 99, "Public admin")]:
        if lo <= s <= hi:
            return name
    return "All"


def group_keys(sic: int) -> list[str]:
    """Most specific first: SIC 2-digit industry, then division, then everyone."""
    return ([f"sic2:{sic // 100:02d}"] if sic else []) + [f"div:{division(sic)}", "All"]


def pick_group(sic: int, tables: dict, min_peers: int = 15) -> str:
    for g in group_keys(sic):
        t = tables.get(g, {})
        if t and max(len(v) for v in t.values()) >= min_peers:
            return g
    return "All"


def load_peers(path) -> tuple[str, dict, int] | None:
    """(as_of, group -> metric -> sorted values, min_peers) from backtest/results/peers.json."""
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return None
    raw = json.loads(p.read_text())
    fix = lambda v: math.inf if v >= 1e18 else -math.inf if v <= -1e18 else v  # noqa: E731
    groups = {g: {k: [fix(v) for v in vals] for k, vals in t.items()} for g, t in raw["groups"].items()}
    return raw["as_of"], groups, raw.get("min_peers", 15)


def group_label(g: str) -> str:
    kind, _, name = g.partition(":")
    return {"sic2": f"SIC {name}", "div": name}.get(kind, "all")
