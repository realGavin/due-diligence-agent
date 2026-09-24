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
        memo = team.run(research=not args.no_research)
        (out / f"{pack.ticker}.md").write_text(render(memo, pack, team.report, llm.model))
        trace = {"evidence": pack.to_dict(), "memo": asdict(memo), "grounding": asdict(team.report),
                 "llm_trace": team.trace, "model": llm.model}
        (out / f"{pack.ticker}.trace.json").write_text(json.dumps(trace, indent=2))
        verdict = memo.scorecard.verdict if memo.scorecard else memo.verdict
        answered = sum(1 for r in memo.research if r.claims)
        print(f"[{t}] {verdict} (score {memo.scorecard.pct:.0%}) · research answered {answered}/{len(memo.research)} · grounding {team.report.kept}/{team.report.proposed} → {out / pack.ticker}.md",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
