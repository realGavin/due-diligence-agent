"""ddagent TICKER [TICKER ...]: write a grounded due-diligence memo for each ticker."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .agents import Team
from .edgar import Edgar
from .evidence import EvidencePack, build_facts
from .filing import build_excerpts
from .ledger import Entry, record
from .llm import AnthropicLLM
from .render import render
from .scorecard import load_peers, metrics, pick_group, score_relative

PEERS = "backtest/results/peers.json"
SUMMARY = "backtest/results/summary.json"


def build_pack(edgar: Edgar, ticker: str) -> tuple[EvidencePack, int]:
    co = edgar.company(ticker)
    filing = edgar.latest_filing(co.cik)
    pack = EvidencePack(co.name, co.ticker, filing.url)
    pack.facts = build_facts(edgar.company_facts(co.cik))
    pack.excerpts = build_excerpts(edgar.filing_html(filing))
    return pack, co.cik


def relative_scorecard(edgar: Edgar, cik: int, pack: EvidencePack, objections):
    """Score against industry peers when the backtest's peer tables are present."""
    loaded = load_peers(PEERS)
    if not loaded:
        return None
    as_of, groups, min_peers = loaded
    g = pick_group(edgar.sic(cik), groups, min_peers)
    return score_relative(metrics(pack), groups[g], g, objections, min_peers)


def calibration() -> dict | None:
    p = Path(SUMMARY)
    return json.loads(p.read_text()) if p.exists() else None


def load_dotenv(path: str = ".env") -> None:
    """Read KEY=VALUE lines from .env (git-ignored) without overriding the real environment."""
    import os

    if not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="ddagent", description=__doc__)
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--out", default="memos")
    ap.add_argument("--no-research", action="store_true", help="skip web research (valuation + question answering)")
    ap.add_argument("--no-ledger", action="store_true", help="don't record the verdict in ledger.jsonl")
    ap.add_argument("--model", default=None, help="Anthropic model id (default: $DD_MODEL or claude-sonnet-5)")
    args = ap.parse_args(argv)

    edgar, llm = Edgar(), AnthropicLLM(args.model)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for t in args.tickers:
        print(f"[{t}] building evidence pack…", file=sys.stderr)
        pack, cik = build_pack(edgar, t)
        print(f"[{t}] {len(pack.facts)} facts, {len(pack.excerpts)} excerpts; running agents…", file=sys.stderr)
        team = Team(llm, pack)
        memo = team.run(research=not args.no_research)
        rel = relative_scorecard(edgar, cik, pack, memo.objections) if memo.scorecard else None
        (out / f"{pack.ticker}.md").write_text(render(memo, pack, team.report, llm.model, rel, calibration()))
        trace = {"evidence": pack.to_dict(), "memo": asdict(memo), "grounding": asdict(team.report),
                 "llm_trace": team.trace, "model": llm.model}
        (out / f"{pack.ticker}.trace.json").write_text(json.dumps(trace, indent=2))
        verdict = memo.scorecard.verdict if memo.scorecard else memo.verdict
        if memo.scorecard and not args.no_ledger:
            record(Entry(pack.ticker, date.today().isoformat(), pack.filing_url, verdict,
                         round(memo.scorecard.pct, 4), memo.verdict, rel.verdict if rel else None,
                         round(rel.pct, 4) if rel else None, model=llm.model))
        answered = sum(1 for r in memo.research if r.claims)
        print(f"[{t}] {verdict} (score {memo.scorecard.pct:.0%}) · research answered {answered}/{len(memo.research)} · grounding {team.report.kept}/{team.report.proposed} → {out / pack.ticker}.md",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
