"""The verdict comes from a fixed rubric computed in code, not from the model's opinion.

Each available dimension scores 0-2 from facts in the evidence pack. High-severity red-team
objections subtract. The verdict follows from the share of available points:
    >= 65%  Dig deeper   ·   40-65%  Watch   ·   < 40%  Pass
Missing dimensions (a bank has no gross margin; no market cap was found) are left out
of the denominator instead of counting as zero.

The thresholds are generic across industries on purpose. The scorecard's job is to make
the triage transparent and repeatable, not to be the last word; a reader can see
exactly why a company landed where it did and disagree with a specific line.
"""
from __future__ import annotations

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
