"""ddagent TICKER [TICKER ...]: write a grounded due-diligence memo for each ticker."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .agents import Team
from .edgar import Edgar
from .evidence import EvidencePack, build_facts
from .filing import build_excerpts
from .llm import AnthropicLLM
from .render import render


def build_pack(edgar: Edgar, ticker: str) -> EvidencePack:
    co = edgar.company(ticker)
    filing = edgar.latest_filing(co.cik)
    pack = EvidencePack(co.name, co.ticker, filing.url)
    pack.facts = build_facts(edgar.company_facts(co.cik))
    pack.excerpts = build_excerpts(edgar.filing_html(filing))
    return pack


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ddagent", description=__doc__)
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--out", default="memos")
    ap.add_argument("--model", default=None, help="Anthropic model id (default: $DD_MODEL or claude-sonnet-5)")
    args = ap.parse_args(argv)

    edgar, llm = Edgar(), AnthropicLLM(args.model)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for t in args.tickers:
        print(f"[{t}] building evidence pack…", file=sys.stderr)
        pack = build_pack(edgar, t)
        print(f"[{t}] {len(pack.facts)} facts, {len(pack.excerpts)} excerpts; running agents…", file=sys.stderr)
        team = Team(llm, pack)
        memo = team.run()
        (out / f"{pack.ticker}.md").write_text(render(memo, pack, team.report, llm.model))
        trace = {"evidence": pack.to_dict(), "memo": asdict(memo), "grounding": asdict(team.report),
                 "llm_trace": team.trace}
        (out / f"{pack.ticker}.trace.json").write_text(json.dumps(trace, indent=2))
        print(f"[{t}] {memo.verdict} · grounding {team.report.kept}/{team.report.proposed} → {out / pack.ticker}.md",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
