"""Planted-error eval: how often does the grounding gate catch a corrupted claim?

It takes every claim that PASSED the gate in real runs (memos/*.trace.json), corrupts
each one in controlled ways, and re-runs the gate against that run's own evidence pack.
No model calls, fully deterministic (fixed seed).

Corruptions:
  wrong_number    one number nudged by -20%, -10%, +15% or +50%, formatted the same way
  wrong_source    citations swapped for other evidence of the same kind (fact->fact, excerpt->excerpt)
  no_source       citations removed
  phantom_source  cites an id that doesn't exist

Each corruption is scored twice: with the numbers-and-ids gate alone (the original gate)
and with the support check added (verify.check_support). The support check can also reject
genuine claims, so the report counts those too, and lists every claim from the published
runs that the new gate rejects so each one can be read by hand.

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

from ddagent import verify  # noqa: E402
from ddagent.evidence import EvidencePack, Excerpt, Fact  # noqa: E402
from ddagent.verify import check_claim, numbers_in  # noqa: E402

FACTORS = (0.8, 0.9, 1.15, 1.5)
THRESHOLDS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40)

# Every published claim the support check rejects, read by hand against its cited passage.
# A new rejection that isn't listed here shows up as "not yet reviewed" in RESULTS.md.
WRONG = "wrong passage: the claim's content isn't in it"
MISQUOTE = "misquote: the quoted words aren't in the passage"
CUT = "can't verify: the quote runs past where the stored passage was cut off"
REVIEW = {
    ("ANET", "W7"): WRONG, ("ANET", "W26"): WRONG, ("ANET", "W48"): WRONG, ("BYND", "W52"): WRONG,
    ("COST", "W17"): WRONG, ("NKE", "W25"): WRONG,
    ("BYND", "W42"): MISQUOTE, ("NVDA", "W71"): MISQUOTE,
    ("BYND", "W35"): "misquote: two sentences spliced into one quote, with added words",
    ("ANET", "W9"): CUT, ("ANET", "W18"): CUT, ("BYND", "W36"): CUT, ("NKE", "W36"): CUT,
}


def load(trace_path: Path):
    d = json.loads(trace_path.read_text())
    ev = d["evidence"]
    pack = EvidencePack(ev["company"], ev["ticker"], ev["filing_url"],
                        [Fact(**f) for f in ev["facts"]], [Excerpt(**e) for e in ev["excerpts"]])
    m = d["memo"]
    judged = [dict(m["thesis"], judgment=True), dict(m["verdict_rationale"], judgment=True)]
    claims = [*judged, *m["bull"], *m["bear"], *m["analyst_claims"], *m["objections"]]
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


def has_numbers_or_judgment(text, judgment, cites) -> bool:
    return bool(numbers_in(text)) or judgment or not any(x[0] in "SW" for x in cites)


def gate(text, cites, pack, judgment, support=True) -> bool:
    return check_claim(text, cites, pack, support=support, judgment=judgment).ok


def main() -> int:
    rng = random.Random(7)
    traces = sorted((ROOT / "memos").glob("*.trace.json"))
    if not traces:
        print("no traces in memos/; run ddagent first", file=sys.stderr)
        return 1
    kinds = ("wrong_number", "wrong_source (claims with numbers)", "wrong_source (qualitative claims)",
             "no_source", "phantom_source")
    tally = {k: [0, 0, 0] for k in kinds}  # caught by old gate, caught by new gate, total
    total_claims = 0
    old_rejects: list[str] = []
    new_rejects: list[str] = []
    misses: list[str] = []
    sweep: list[tuple] = []  # (pack, text, cites, judgment, swapped cites) for the threshold table
    for tp in traces:
        pack, claims = load(tp)
        for c in claims:
            text, cites, judgment = c["text"], c["citations"], c.get("judgment", False)
            total_claims += 1
            if not gate(text, cites, pack, judgment, support=False):  # a looser, older gate let it through
                old_rejects.append(f"{pack.ticker}: {check_claim(text, cites, pack, support=False).reason} · {text[:140]}")
                continue
            v = check_claim(text, cites, pack, judgment=judgment)
            if not v.ok:  # passes numbers and ids, fails the support check: list it for review
                verdict = REVIEW.get((pack.ticker, cites[0]), "NOT YET REVIEWED") if len(cites) == 1 else "NOT YET REVIEWED"
                new_rejects.append((verdict, f"**{pack.ticker}** {cites} · {v.reason}\n  - Claim: {text[:220]}"))
                if not has_numbers_or_judgment(text, judgment, cites):
                    sweep.append((pack, text, cites, None))
                continue
            has_numbers = bool(numbers_in(text))

            def trial(kind, t, cs):
                tally[kind][2] += 1
                tally[kind][0] += not gate(t, cs, pack, judgment, support=False)
                caught = not gate(t, cs, pack, judgment)
                tally[kind][1] += caught
                if not caught:
                    misses.append(f"{pack.ticker} · {kind}: {t[:140]} {cs}")

            for _ in range(2):
                bad = nudge(text, rng)
                if bad:
                    trial("wrong_number", bad, cites)
            swapped = swap(cites, pack, rng)
            trial("wrong_source (claims with numbers)" if has_numbers else "wrong_source (qualitative claims)",
                  text, swapped)
            trial("no_source", text, [])
            trial("phantom_source", text, cites[:-1] + ["F9999"])
            if not has_numbers_or_judgment(text, judgment, cites):
                sweep.append((pack, text, cites, swapped))

    # How the cutoff trades catches against wrongly rejected claims. Uses the claims that passed
    # the default cutoff, plus everything the support check rejected, so both sides are visible.
    rows = []
    default = verify.SUPPORT_MIN
    for t in THRESHOLDS:
        verify.SUPPORT_MIN = t
        swaps = [x for x in sweep if x[3] is not None]
        caught = sum(not verify.check_support(text, [p.get(c) for c in sw], p).ok for p, text, _, sw in swaps)
        rejected = sum(not verify.check_support(text, [p.get(c) for c in cs], p).ok for p, text, cs, _ in sweep)
        rows.append((t, caught, len(swaps), rejected, len(sweep)))
    verify.SUPPORT_MIN = default

    n_ok = total_claims - len(old_rejects)
    lines = ["# Planted-error eval", "",
             f"Source: {len(traces)} real runs ({', '.join(t.name.split('.')[0] for t in traces)}), "
             f"{total_claims} unique claims. Seed 7, no model calls.", "",
             "## What the gate catches", "",
             f"Corruptions are applied to the {n_ok - len(new_rejects)} claims that pass the current gate. "
             "*Before* is the numbers-and-ids gate alone; *after* adds the support check "
             "(a direct quote must appear in the cited passage; a qualitative claim must share enough "
             f"of its distinctive words with the passages it cites, cutoff {default:.0%}).", "",
             "| Corruption | Before | After |", "|---|---|---|"]
    for k, (old, new, total) in tally.items():
        if total:
            lines.append(f"| {k} | {old}/{total} ({old / total:.0%}) | {new}/{total} ({new / total:.0%}) |")
    lines += ["", "## What it rejects in the published memos", "",
              f"Of the {n_ok} claims in the published runs that passed the original gate, the support check "
              f"rejects {len(new_rejects)}. Each one was read against its cited passage; see the list below. "
              "The PM's thesis and verdict rationale summarize findings that already passed the gate, so they "
              "get the quote check but not the word-overlap check.", ""]
    counts: dict[str, int] = {}
    for verdict, _ in new_rejects:
        counts[verdict] = counts.get(verdict, 0) + 1
    lines += ["| Hand review | Claims |", "|---|---|"] + [f"| {k} | {v} |" for k, v in counts.items()] + [""]
    lines += [f"- *{verdict}* · {r}" for verdict, r in new_rejects]
    lines += ["", "## Choosing the cutoff", "",
              f"Qualitative factual claims citing passages, as published ({len(sweep)}). *Swaps caught* is the "
              "wrong-source corruption on the claims that pass at the default cutoff. *Published claims rejected* "
              "is how many unmodified claims each cutoff drops, including quote failures, which don't depend on "
              "the cutoff. At the default, every one of them is in the hand-reviewed list above; stricter "
              "cutoffs start dropping claims that are genuinely supported. The cutoff was picked on these same five runs, so treat the table as a "
              "description of this data, not an out-of-sample result.", "",
              "| Cutoff | Swaps caught | Published claims rejected |", "|---|---|---|"]
    lines += [f"| {t:.0%} | {c}/{n} | {r}/{m} |" for t, c, n, r, m in rows]
    lines += ["", "The check verifies that a claim and its passage are about the same thing, not that the passage "
                  "says what the claim says: a claim that reuses the passage's words and gets it wrong still passes."]
    if old_rejects:
        lines += ["", "## Claims the older gate wrongly accepted (numbers)", ""] + [f"- {r}" for r in old_rejects]
    if misses:
        lines += ["", "## Misses (corrupted claims that got through the new gate)", ""] + [f"- {m}" for m in misses[:60]]
    (ROOT / "eval" / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:16 + len(tally)]))
    print("\n".join(f"{t:.0%}: caught {c}/{n}, published rejected {r}/{m}" for t, c, n, r, m in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
