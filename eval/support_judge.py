"""Meaning-check eval: word overlap vs. a model judge, on the same claims.

Four sets, all against the evidence packs saved in memos/*.trace.json:

  published   every claim from the five runs that cites a passage (thesis and verdict
              rationale excluded, as in the gate), as written. Most should be accepted; the
              13 hand-reviewed bad ones (eval/planted_errors.py REVIEW) should not.
  swapped     the same claims with their citations swapped for other passages (seed 7).
              All should be rejected.
  paraphrase  30 hand-written rewrites of real claims in different words, same meaning.
              All should be accepted. (eval/paraphrase_cases.json)
  reversal    30 hand-written claims that reuse the passage's words but say something it
              doesn't. All should be rejected.

Both checks run after the code checks (ids, numbers, verbatim quotes). A case those reject is
counted as rejected for both, since neither check would ever see it.

Judge answers are cached in eval/judge_cache.json (model + prompt + claim + passages), so
anyone can rerun this without an API key and get the same table:

    python eval/support_judge.py --offline       # from the committed cache
    python eval/support_judge.py                 # calls the API for anything not cached
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from ddagent.evidence import Excerpt  # noqa: E402
from ddagent.judge import SupportJudge  # noqa: E402
from ddagent.verify import check_claim  # noqa: E402
import planted_errors as pe  # noqa: E402

CACHE = ROOT / "eval" / "judge_cache.json"


class Offline:
    """Stands in for the API in --offline mode: any uncached call is an error."""
    def __init__(self, model):
        self.model = model

    def complete(self, system, user):
        raise SystemExit("--offline: a judge answer is missing from eval/judge_cache.json; rerun without --offline")


def cases(memos: Path, hand_sets: bool = True):
    packs, sets = {}, {"published": [], "swapped": [], "paraphrase": [], "reversal": []}
    rng = random.Random(7)
    for tp in sorted(memos.glob("*.trace.json")):
        pack, claims = pe.load(tp)
        packs[pack.ticker] = pack
        for c in claims:
            if c.get("judgment") or not any(x[0] in "SW" for x in c["citations"]):
                continue
            if not check_claim(c["text"], c["citations"], pack, support=False).ok:
                continue  # an older, looser gate let it through; the numbers check rejects it now
            label = None  # the hand review covered exactly the claims the word-overlap gate rejects
            if len(c["citations"]) == 1 and not check_claim(c["text"], c["citations"], pack).ok:
                label = pe.REVIEW.get((pack.ticker, c["citations"][0]), "NOT YET REVIEWED")
            sets["published"].append((pack.ticker, c["text"], c["citations"], label))
            sw = pe.swap(c["citations"], pack, rng)
            if sw != c["citations"]:
                sets["swapped"].append((pack.ticker, c["text"], sw, None))
    if not hand_sets:  # fresh memos: the hand-written cases belong to the original five runs
        del sets["paraphrase"], sets["reversal"]
        return packs, sets
    hand = json.loads((ROOT / "eval" / "paraphrase_cases.json").read_text())
    for k in ("paraphrase", "reversal"):
        sets[k] = [(t, text, [cid], None) for t, cid, text in hand[k]]
    return packs, sets


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("DD_JUDGE_MODEL", "claude-haiku-5-5"))
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--memos", default="memos", help="folder of *.trace.json runs to test (default: memos)")
    ap.add_argument("--out", default="eval/JUDGE_RESULTS.md")
    args = ap.parse_args(argv)

    if args.offline:
        llm = Offline(args.model)
    else:
        from ddagent.cli import load_dotenv
        from ddagent.llm import AnthropicLLM
        load_dotenv(str(ROOT / ".env"))
        llm = AnthropicLLM(args.model, max_tokens=1500)
    judge = SupportJudge(llm, CACHE, model_name=args.model)
    memos = ROOT / args.memos
    packs, sets = cases(memos, hand_sets=(memos.resolve() == (ROOT / "memos").resolve()))

    def run(case):
        t, text, cites, _ = case
        pack = packs[t]
        overlap = check_claim(text, cites, pack)
        judged = check_claim(text, cites, pack, judge=judge)
        return overlap, judged

    results = {}
    with ThreadPoolExecutor(max_workers=1 if args.offline else args.workers) as ex:
        for name, cs in sets.items():
            results[name] = list(ex.map(run, cs))
            judge.save()
    judge.save()

    want = {"published": None, "swapped": False, "paraphrase": True, "reversal": False}
    lines = ["# Meaning-check eval", "",
             f"Judge model: `{args.model}`. Word overlap = the cutoff check in `verify.py`. Both run after the "
             "code checks (ids, numbers, verbatim quotes). Rerun with `python eval/support_judge.py --offline`.", "",
             "| Set | Should be | Word overlap | Model judge |", "|---|---|---|---|"]
    for name, rs in results.items():
        n = len(rs)
        if name == "published":
            bad = [i for i, c in enumerate(sets[name]) if c[3]]
            good = [i for i, c in enumerate(sets[name]) if not c[3]]
            for idx, label, verb in ((good, "accepted (not flagged in hand review)", "accepted"),
                                     (bad, "rejected (hand-reviewed as wrong)", "rejected")):
                o = sum(rs[i][0].ok == (verb == "accepted") for i in idx)
                j = sum(rs[i][1].ok == (verb == "accepted") for i in idx)
                lines.append(f"| published claims | {label} | {o}/{len(idx)} {verb} | {j}/{len(idx)} {verb} |")
            continue
        verb = "accepted" if want[name] else "rejected"
        o = sum(r[0].ok == want[name] for r in rs)
        j = sum(r[1].ok == want[name] for r in rs)
        lines.append(f"| {name} | {verb} | {o}/{n} ({o / n:.0%}) | {j}/{n} ({j / n:.0%}) |")

    def listing(title, rows):
        out = ["", f"## {title}", ""]
        out += [f"- **{t}** {cites} · {v.reason}\n  - Claim: {text[:240]}" for (t, text, cites, _), v in rows] or ["None."]
        return out

    pub = list(zip(sets["published"], results["published"]))
    lines += listing("Published claims the judge rejects that hand review hadn't flagged (read each one)",
                     [(c, r[1]) for c, r in pub if not c[3] and not r[1].ok])
    lines += listing("Published claims hand review flagged that the judge accepts",
                     [(c, r[1]) for c, r in pub if c[3] and r[1].ok])
    lines += listing("Paraphrases the judge wrongly rejects",
                     [(c, r[1]) for c, r in zip(sets.get("paraphrase", []), results.get("paraphrase", [])) if not r[1].ok])
    lines += listing("Reversals the judge misses",
                     [(c, r[1]) for c, r in zip(sets.get("reversal", []), results.get("reversal", [])) if r[1].ok])
    lines += listing("Swapped citations the judge misses",
                     [(c, r[1]) for c, r in zip(sets["swapped"], results["swapped"]) if r[1].ok])
    if memos.resolve() != (ROOT / "memos").resolve():
        accepted = [(c, r[1]) for c, r in pub if r[1].ok]
        lines += listing("A random sample of 25 claims the judge accepts (read each one)",
                         random.Random(11).sample(accepted, min(25, len(accepted))))
        lines.insert(2, f"Runs: `{args.memos}` (fresh memos, generated with the meaning check off; nothing in the "
                        "judge's instructions was tuned on them).\n")
    (ROOT / args.out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    print(f"\njudge API calls this run: {judge.calls}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
