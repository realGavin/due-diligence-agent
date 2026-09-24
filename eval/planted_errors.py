"""Planted-error eval: how often does the grounding gate catch a corrupted claim?

It takes every claim that PASSED the gate in real runs (memos/*.trace.json), corrupts
each one in controlled ways, and re-runs the gate against that run's own evidence pack.
No model calls, fully deterministic (fixed seed).

Corruptions:
  wrong_number    one number nudged by -20%, -10%, +15% or +50%, formatted the same way
  wrong_source    citations swapped for other evidence of the same kind (fact->fact, excerpt->excerpt)
  no_source       citations removed
  phantom_source  cites an id that doesn't exist

Honest scope: the gate verifies numbers and ids. A qualitative claim with no numbers
and a swapped citation is not detectable by this gate, and the report counts those
separately instead of hiding them.

    python eval/planted_errors.py            # writes eval/RESULTS.md
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ddagent.evidence import EvidencePack, Excerpt, Fact  # noqa: E402
from ddagent.verify import check_claim, numbers_in  # noqa: E402

FACTORS = (0.8, 0.9, 1.15, 1.5)


def load(trace_path: Path):
    d = json.loads(trace_path.read_text())
    ev = d["evidence"]
    pack = EvidencePack(ev["company"], ev["ticker"], ev["filing_url"],
                        [Fact(**f) for f in ev["facts"]], [Excerpt(**e) for e in ev["excerpts"]])
    m = d["memo"]
    claims = [m["thesis"], m["verdict_rationale"], *m["bull"], *m["bear"], *m["analyst_claims"], *m["objections"]]
    for r in m.get("research", []):
        claims += r.get("claims", [])
    seen, out = set(), []
    for c in claims:
        key = (c["text"], tuple(c["citations"]))
        if key not in seen:
            seen.add(key)
            out.append(c)
    return pack, out


def nudge(text: str, rng: random.Random) -> str | None:
    nums = numbers_in(text)
    if not nums:
        return None
    n = rng.choice(nums)
    m = re.search(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", n.raw)
    digits = m.group(0)
    decimals = len(digits.split(".")[1]) if "." in digits else 0
    val = float(digits.replace(",", "")) * rng.choice(FACTORS)
    new = f"{val:,.{decimals}f}" if "," in digits else f"{val:.{decimals}f}"
    if new == digits:
        return None
    return text[:n.start] + n.raw.replace(digits, new, 1) + text[n.start + len(n.raw):]


def swap(citations: list[str], pack: EvidencePack, rng: random.Random) -> list[str]:
    out = []
    for c in citations:
        pool = [x.id for x in (pack.facts if c.startswith("F") else pack.excerpts)
                if x.id[0] == c[0] and x.id not in citations]
        out.append(rng.choice(pool) if pool else c)
    return out


def main() -> int:
    rng = random.Random(7)
    traces = sorted((ROOT / "memos").glob("*.trace.json"))
    if not traces:
        print("no traces in memos/; run ddagent first", file=sys.stderr)
        return 1
    tally = {k: [0, 0] for k in ("wrong_number", "wrong_source (claims with numbers)",
                                 "wrong_source (qualitative claims)", "no_source", "phantom_source")}
    controls = [0, 0]
    misses: list[str] = []
    regressions: list[str] = []
    for tp in traces:
        pack, claims = load(tp)
        for c in claims:
            text, cites = c["text"], c["citations"]
            controls[1] += 1
            v = check_claim(text, cites, pack)
            if not v.ok:  # a claim an earlier, looser gate let through; nothing to corrupt
                regressions.append(f"{pack.ticker}: {v.reason} · {text[:140]}")
                continue
            controls[0] += 1
            has_numbers = bool(numbers_in(text))

            def trial(kind, t, cs):
                tally[kind][1] += 1
                if not check_claim(t, cs, pack).ok:
                    tally[kind][0] += 1
                elif kind != "wrong_source (qualitative claims)":
                    misses.append(f"{pack.ticker} · {kind}: {t[:140]} {cs}")

            for _ in range(2):
                bad = nudge(text, rng)
                if bad:
                    trial("wrong_number", bad, cites)
            trial("wrong_source (claims with numbers)" if has_numbers else "wrong_source (qualitative claims)",
                  text, swap(cites, pack, rng))
            trial("no_source", text, [])
            trial("phantom_source", text, cites[:-1] + ["F9999"])

    lines = ["# Planted-error eval", "",
             f"Source: {len(traces)} real runs ({', '.join(t.name.split('.')[0] for t in traces)}); "
             f"{controls[1]} claims that passed the gate, corrupted and re-checked. Seed 7, no model calls.", "",
             f"Control: {controls[0]}/{controls[1]} unmodified claims pass the current gate."
             + (f" The other {len(regressions)} were accepted by the older gate that produced these runs and are "
                "now rejected (listed below); they are excluded from the corruption trials." if regressions else ""), "",
             "| Corruption | Caught | Rate |", "|---|---|---|"]
    for k, (caught, total) in tally.items():
        if total:
            lines.append(f"| {k} | {caught}/{total} | {caught / total:.0%} |")
    lines += ["", "Qualitative claims (no numbers) with a swapped source pass by design: the gate checks numbers "
                  "and ids, not meaning. That row is here so the limit is visible."]
    if regressions:
        lines += ["", "## Claims the older gate wrongly accepted", ""] + [f"- {r}" for r in regressions]
    if misses:
        lines += ["", "## Misses (corrupted claims that got through)", ""] + [f"- {m}" for m in misses[:40]]
    (ROOT / "eval" / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12 + len(tally)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
