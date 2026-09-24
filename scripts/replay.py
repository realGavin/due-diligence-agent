"""Re-grade saved runs with the current code, without calling the model.

Every run's trace.json holds the evidence pack and every raw model reply. Replay feeds
those replies back through the pipeline: same answers, but the current grounding gate,
scorecard and renderer. Improving the gate therefore re-grades old memos for free, and a
memo can be audited by anyone with the trace, with no API key.

    python scripts/replay.py memos/*.trace.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ddagent.agents import Team  # noqa: E402
from ddagent.evidence import EvidencePack, Excerpt, Fact  # noqa: E402
from ddagent.llm import Segment, Source  # noqa: E402
from ddagent.render import VALUATION, render  # noqa: E402

# System-prompt markers, checked in this order (the final-memo prompt also says "red team").
STAGES = [("final investment memo", "PM final"), ("portfolio manager. Write", "PM draft"),
          ("Business analyst", "Business analyst"), ("Financial analyst", "Financial analyst"),
          ("Risk analyst", "Risk analyst"), ("red team", "Red team")]


class ReplayLLM:
    def __init__(self, trace: list[dict], model: str):
        self.model = model
        self.replies: dict[str, deque] = defaultdict(deque)
        self.research_replies: dict[str, list[Segment]] = {}
        for t in trace:
            stage = t["stage"].removesuffix(" (retry)")
            if stage in ("Research", "Valuation"):
                segs = [Segment(s["text"], [Source(**x) for x in s["sources"]]) for s in t["reply"]]
                self.research_replies[t["question"]] = segs
            else:
                self.replies[stage].append(t["reply"])

    def complete(self, system: str, user: str) -> str:
        stage = next(name for key, name in STAGES if key in system)
        if not self.replies[stage]:
            raise RuntimeError(f"no recorded reply left for {stage}")
        return self.replies[stage].popleft()

    def research(self, system: str, question: str) -> list[Segment]:
        return self.research_replies.get(question, [Segment("UNANSWERED: not in recorded trace")])


def replay(path: Path) -> str:
    d = json.loads(path.read_text())
    ev = d["evidence"]
    # Start from the evidence as it was before research: no web excerpts, no valuation facts.
    facts = [Fact(**f) for f in ev["facts"] if f["label"] not in VALUATION]
    excerpts = [Excerpt(**e) for e in ev["excerpts"] if e["section"] != "Web"]
    pack = EvidencePack(ev["company"], ev["ticker"], ev["filing_url"], facts, excerpts)
    model = d.get("model", "claude-sonnet-5")
    team = Team(ReplayLLM(d["llm_trace"], model), pack)
    memo = team.run(research=any(t["stage"] in ("Research", "Valuation") for t in d["llm_trace"]))
    (path.parent / f"{pack.ticker}.md").write_text(render(memo, pack, team.report, model))
    d.update({"evidence": pack.to_dict(), "memo": asdict(memo), "grounding": asdict(team.report), "model": model})
    path.write_text(json.dumps(d, indent=2))
    sc = memo.scorecard
    return (f"{pack.ticker}: {sc.verdict if sc else memo.verdict} ({sc.pct:.0%}) · "
            f"grounding {team.report.kept}/{team.report.proposed}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(replay(Path(p)))
