"""Every verdict is a prediction. The ledger records it; `ddagent grade` scores it when it comes due.

Each memo run appends one line to ledger.jsonl: the scorecard's verdict, the sector-relative
verdict, the PM's own view, the date, and a 12-month horizon. Grading compares the stock's
total return over that window with SPY's, and reports, per verdict, how often the call
was right, including the cases where the scorecard and the PM disagreed.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .prices import Prices

LEDGER = Path("ledger.jsonl")
BENCHMARK = "SPY"


@dataclass
class Entry:
    ticker: str
    run_date: str
    filing_url: str
    scorecard_verdict: str
    scorecard_pct: float
    pm_view: str
    relative_verdict: str | None = None
    relative_pct: float | None = None
    horizon_months: int = 12
    model: str = ""
    graded: dict = field(default_factory=dict)

    @property
    def due(self) -> str:
        y, m = int(self.run_date[:4]), int(self.run_date[5:7]) + self.horizon_months
        y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
        return f"{y}-{m:02d}-{self.run_date[8:10]}"


def load(path: Path = LEDGER) -> list[Entry]:
    if not path.exists():
        return []
    return [Entry(**json.loads(line)) for line in path.read_text().splitlines() if line.strip()]


def save(entries: list[Entry], path: Path = LEDGER) -> None:
    path.write_text("".join(json.dumps(asdict(e)) + "\n" for e in entries))


def record(entry: Entry, path: Path = LEDGER) -> None:
    entries = [e for e in load(path) if not (e.ticker == entry.ticker and e.run_date == entry.run_date)]
    save(entries + [entry], path)


def window_return(prices: Prices, ticker: str, start: str, end: str) -> float | None:
    """Total return from the month-end on/before start to the month-end on/before end."""
    s = prices.monthly(ticker, start="2000-01-01")
    if not s:
        return None
    i, j = s.index_at(start), s.index_at(end)
    if i is None or j is None or j <= i:
        return None
    return s.adjclose[j] / s.adjclose[i] - 1


def _right(verdict: str, excess: float) -> bool:
    # Dig deeper should beat the market, Pass should trail it; Watch is right within ±5 points.
    return excess > 0 if verdict == "Dig deeper" else excess < 0 if verdict == "Pass" else abs(excess) <= 0.05


def grade(entries: list[Entry], prices: Prices, today: str | None = None) -> list[Entry]:
    today = today or date.today().isoformat()
    for e in entries:
        if e.graded or e.due > today:
            continue
        r = window_return(prices, e.ticker, e.run_date, e.due)
        b = window_return(prices, BENCHMARK, e.run_date, e.due)
        if r is None or b is None:
            continue
        ex = r - b
        e.graded = {"return": round(r, 4), "benchmark": round(b, 4), "excess": round(ex, 4),
                    "scorecard_right": _right(e.scorecard_verdict, ex), "pm_right": _right(e.pm_view, ex),
                    "graded_on": today}
        if e.relative_verdict:
            e.graded["relative_right"] = _right(e.relative_verdict, ex)
    return entries


def summarize(entries: list[Entry]) -> str:
    done = [e for e in entries if e.graded]
    pending = [e for e in entries if not e.graded]
    lines = [f"{len(done)} graded, {len(pending)} pending"]
    if pending:
        lines.append("next due: " + ", ".join(f"{e.ticker} {e.due}" for e in sorted(pending, key=lambda e: e.due)[:5]))
    if not done:
        return "\n".join(lines)
    for who, key in (("scorecard", "scorecard_right"), ("sector-relative", "relative_right"), ("PM", "pm_right")):
        xs = [e.graded[key] for e in done if key in e.graded]
        if xs:
            lines.append(f"{who}: right {sum(xs)}/{len(xs)}")
    dis = [e for e in done if e.scorecard_verdict != e.pm_view]
    if dis:
        s = sum(e.graded["scorecard_right"] for e in dis)
        p = sum(e.graded["pm_right"] for e in dis)
        lines.append(f"when the scorecard and PM disagreed ({len(dis)}): scorecard right {s}, PM right {p}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ddagent-grade", description=__doc__)
    ap.add_argument("--ledger", default=str(LEDGER))
    args = ap.parse_args(argv)
    path = Path(args.ledger)
    entries = grade(load(path), Prices())
    save(entries, path)
    print(summarize(entries), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
