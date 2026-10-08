"""Run the three signals on every company in the holdout sample.

  scorecard  the code-only rubric (no model), exactly as in the memos
  single     one prompt, same evidence pack: "Dig deeper, Watch or Pass?"  (the baseline
             anyone would try first)
  team       the full pipeline: three analysts -> PM draft -> red team -> PM final,
             every claim through the grounding gate; web research is OFF because the web
             of today would leak what happened after the filing

Results append to holdout/results/runs.jsonl, one line per company, so an interrupted
run resumes where it stopped.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

from ddagent.agents import JUDGMENT_PROMPT, JUDGMENT_SCHEMA, Team, clean_judgment
from ddagent.evidence import EvidencePack
from ddagent.llm import parse_json
from ddagent.scorecard import metrics, score

from .sample import CACHE, load_pack

RESULTS = Path("holdout/results")
RUNS = RESULTS / "runs.jsonl"
MODEL = "claude-sonnet-4-5-20250929"  # training data ends July 2025: the filings are unseen
PRICE = {"input": 3.0, "output": 15.0}  # USD per million tokens, Sonnet 4.5 standard

SINGLE_SYSTEM = (
    "You are an equity analyst doing research triage. Using ONLY the evidence pack below (no outside "
    "knowledge about this company, its stock price or news), decide whether the company deserves an analyst's "
    "deeper work over the next twelve months: 'Dig deeper', 'Watch', or 'Pass'. Also give conviction from 1 "
    "(low) to 5 (high) that the stock beats the US market over the next twelve months. " + JUDGMENT_PROMPT + "\n"
    'Reply with JSON only: {"verdict": "Dig deeper|Watch|Pass", "conviction": 3, "rationale": "two sentences", '
    + JUDGMENT_SCHEMA + "}"
)
ORD = {"Pass": 0, "Watch": 1, "Dig deeper": 2}


def single(llm, pack: EvidencePack) -> dict:
    raw = llm.complete(SINGLE_SYSTEM, pack.to_prompt())
    try:
        out = parse_json(raw)
    except (ValueError, json.JSONDecodeError):
        return {"verdict": None, "conviction": None, "raw": raw[:500]}
    v = out.get("verdict") if out.get("verdict") in ORD else None
    try:
        c = max(1, min(5, int(out.get("conviction"))))
    except (TypeError, ValueError):
        c = None
    score, forecast = clean_judgment(out)
    return {"verdict": v, "conviction": c, "rationale": str(out.get("rationale", ""))[:600],
            "score": score, "forecast": forecast}


def run_company(ticker: str, make_llm) -> dict:
    meta, pack = load_pack(ticker)
    sc = score(pack, [])
    row = {"ticker": ticker, **{k: meta[k] for k in ("cik", "filed", "sic", "mcap")},
           "scorecard": {"verdict": sc.verdict, "pct": round(sc.pct, 4)},
           "metrics": {k: (v if abs(v) < 1e18 else (1e18 if v > 0 else -1e18)) for k, v in metrics(pack).items()}}
    llm = make_llm()
    t0 = time.monotonic()
    row["single"] = single(llm, pack)
    team = Team(llm, pack)
    try:
        memo = team.run(research=False)
        highs = sum(1 for o in memo.objections if (o.severity or "").lower() == "high")
        row["team"] = {"pm_verdict": memo.verdict, "scorecard_with_penalty": round(memo.scorecard.pct, 4),
                       "scorecard_verdict_with_penalty": memo.scorecard.verdict, "high_objections": highs,
                       "objections": len(memo.objections), "grounding": [team.report.kept, team.report.proposed],
                       "score": memo.score, "forecast": memo.forecast,
                       "thesis": memo.thesis.text[:400]}
    except RuntimeError as e:  # no analyst claim survived: recorded, not fatal
        row["team"] = {"error": str(e)}
    row["seconds"] = round(time.monotonic() - t0, 1)
    row["model"] = getattr(llm, "model", "stub")
    row["code_version"] = code_version()
    usage = getattr(llm, "usage", [])
    row["tokens"] = [sum(u[0] for u in usage), sum(u[1] for u in usage)]
    row["calls"] = len(usage)
    trace_dir = RESULTS / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / f"{ticker}.json").write_text(json.dumps({"row": row, "llm_trace": team.trace,
                                                          "grounding": asdict(team.report)}))
    return row


def cost(tokens: tuple[int, int]) -> float:
    return tokens[0] / 1e6 * PRICE["input"] + tokens[1] / 1e6 * PRICE["output"]


def run(tickers: list[str], make_llm, workers: int = 4, budget: float | None = None,
        runs_path: Path = RUNS) -> list[dict]:
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["ticker"] for l in runs_path.read_text().splitlines()} if runs_path.exists() else set()
    todo = [t for t in tickers if t not in done]
    spent, rows = 0.0, []
    print(f"{len(done)} already done, {len(todo)} to run", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=workers) as ex, open(runs_path, "a") as fh:
        futs = {ex.submit(run_company, t, make_llm): t for t in todo}
        for i, f in enumerate(as_completed(futs), 1):
            t = futs[f]
            try:
                row = f.result()
            except Exception as e:  # noqa: BLE001 - one failed company must not stop the batch
                print(f"\n  {t} failed: {type(e).__name__}: {e}", file=sys.stderr)
                continue
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            rows.append(row)
            spent += cost(row["tokens"])
            print(f"\r  {i}/{len(todo)} · ${spent:,.2f} so far", end="", file=sys.stderr)
            if budget is not None and spent >= budget:
                print(f"\n  budget ${budget:,.0f} reached; stopping (rerun to continue)", file=sys.stderr)
                for g in futs:
                    g.cancel()
                break
    print(file=sys.stderr)
    return rows


# ----------------------------------------------------------------------------- dry run

class StubLLM:
    """Stands in for the model: valid JSON for every stage, citing real ids, so the whole
    pipeline runs on real evidence packs without an API call. Counts prompt size so the
    real run's cost can be estimated before spending anything."""

    # Average reply length per stage, in tokens, from the five real v0.2 memo traces.
    OUT_TOKENS = {"Business analyst": 600, "Financial analyst": 440, "Risk analyst": 630,
                  "portfolio manager. Write": 220, "final investment memo": 1870, "red team": 840,
                  "equity analyst doing research triage": 120}

    def __init__(self, pack_ids: list[str] | None = None):
        self.usage: list[tuple[int, int]] = []
        self.ids = pack_ids or ["F1"]

    def complete(self, system: str, user: str) -> str:
        import re

        stage = next((k for k in self.OUT_TOKENS if k in system), "Business analyst")
        self.usage.append((int((len(system) + len(user)) / 3.6), self.OUT_TOKENS[stage]))
        ids = re.findall(r"\[((?:F|S)\d+)\]", user)[:2] or self.ids
        claim = {"text": "The filing describes this point.", "citations": ids[:1]}
        judgment = {"score": 50, "forecast": {"revenue_growth_pct": 5.0, "operating_margin_pct": 10.0}}
        if stage == "equity analyst doing research triage":
            return json.dumps({"verdict": "Watch", "conviction": 3, "rationale": "stub", **judgment})
        if stage == "portfolio manager. Write":
            return json.dumps({"thesis": claim})
        if stage == "red team":
            return json.dumps({"objections": [{**claim, "severity": "medium"}]})
        if stage == "final investment memo":
            return json.dumps({"thesis": claim, "bull": [claim], "bear": [claim], "questions": ["q"],
                               "verdict": "Watch", "verdict_rationale": claim, **judgment})
        return json.dumps({"claims": [claim]})

    def research(self, system, question):  # never used: research is off
        return []


def manifest() -> list[dict]:
    return json.loads((CACHE / "manifest.json").read_text())


# ----------------------------------------------------------------------------- splits

DEV_FRACTION = 0.2
SPLIT_SEED = "ddagent-holdout-2026"
PREREG = Path("holdout/PREREGISTRATION.md")


def split_of(ticker: str) -> str:
    """Deterministic dev/test assignment from a hash of the ticker: independent of sample order,
    of results, and of which companies happen to be in the sample."""
    h = int(hashlib.sha256(f"{SPLIT_SEED}:{ticker}".encode()).hexdigest()[:8], 16) / 16 ** 8
    return "dev" if h < DEV_FRACTION else "test"


def runs_path(split: str) -> Path:
    return RESULTS / f"runs_{split}.jsonl"


def code_version() -> str:
    """git commit plus a hash of the preregistration, recorded with every result."""
    import subprocess

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "ddagent", "holdout"], capture_output=True,
                               text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit, dirty = "unknown", ""
    prereg = hashlib.sha256(PREREG.read_bytes()).hexdigest()[:10] if PREREG.exists() else "none"
    return f"{commit}{'+dirty' if dirty else ''} prereg:{prereg}"


def check_test_run_allowed() -> None:
    """The test split runs once, on committed code, after the preregistration is committed."""
    v = code_version()
    if "prereg:none" in v:
        raise SystemExit(f"{PREREG} is missing: write and commit the preregistration before the test run")
    if "+dirty" in v or v.startswith("unknown"):
        raise SystemExit("commit ddagent/ and holdout/ first, so the test results point to the exact code that produced them")
