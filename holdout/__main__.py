"""python -m holdout {prepare,run,analyze}; see holdout/__init__.py."""
from __future__ import annotations

import argparse
import sys

from ddagent.cli import load_dotenv

from . import analyze, run, sample


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="python -m holdout")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="build the sample and evidence packs (SEC data, no API)")
    p.add_argument("--limit", type=int)
    p.add_argument("--sample", type=int, help="random sample of this many companies (fixed seed)")
    r = sub.add_parser("run", help="run scorecard, single-prompt baseline and agent team")
    r.add_argument("--dry-run", action="store_true", help="stub model: test the pipeline and estimate cost")
    r.add_argument("--split", choices=["dev", "test"], help="dev: iterate freely; test: once, after preregistration")
    r.add_argument("--limit", type=int)
    r.add_argument("--budget", type=float, help="stop once this many USD have been spent")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--model", default=run.MODEL)
    a = sub.add_parser("analyze", help="score completed runs against business outcomes and returns")
    a.add_argument("--dry-run", action="store_true", help="analyze the dry-run file instead")
    a.add_argument("--split", choices=["dev", "test"], default="test")
    a.add_argument("--refresh-prices", action="store_true", help="re-download prices for the sample first")
    args = ap.parse_args(argv)

    if args.cmd == "prepare":
        m = sample.prepare(args.limit, args.sample)
        print(f"{len(m)} companies in the holdout sample (packs in {sample.PACKS})")
        return 0

    if args.cmd == "run":
        tickers = [m["ticker"] for m in run.manifest()]
        if args.split:
            tickers = [t for t in tickers if run.split_of(t) == args.split]
        tickers = tickers[: args.limit]
        if args.dry_run:
            path = run.RESULTS / "runs_dryrun.jsonl"
            if path.exists():
                path.unlink()
            rows = run.run(tickers, run.StubLLM, workers=args.workers, runs_path=path)
            if rows:
                per = [run.cost(r["tokens"]) for r in rows]
                all_t = [m["ticker"] for m in run.manifest()]
                dev = sum(run.split_of(t) == "dev" for t in all_t)
                avg = sum(per) / len(per)
                print(f"dry run OK on {len(rows)} companies, {sum(r['calls'] for r in rows) / len(rows):.1f} calls each")
                print(f"sample: {len(all_t)} companies = {dev} dev + {len(all_t) - dev} test")
                print(f"estimated cost: ${avg:.2f} per company -> dev ${avg * dev:,.0f}, test ${avg * (len(all_t) - dev):,.0f} "
                      "(Sonnet 4.5 standard pricing; output size from real memo traces)")
            return 0
        if not args.split:
            raise SystemExit("choose --split dev or --split test for a real run")
        if args.split == "test":
            run.check_test_run_allowed()
        from ddagent.llm import AnthropicLLM

        make = lambda: AnthropicLLM(args.model)  # noqa: E731 - one client per company keeps usage separate
        rows = run.run(tickers, make, workers=args.workers, budget=args.budget, runs_path=run.runs_path(args.split))
        print(f"{len(rows)} companies run this session; results in {run.runs_path(args.split)}", file=sys.stderr)
        return 0

    path = run.RESULTS / "runs_dryrun.jsonl" if args.dry_run else run.runs_path(args.split)
    return analyze.main(path, refresh=args.refresh_prices, dev_path=run.runs_path("dev"))


if __name__ == "__main__":
    raise SystemExit(main())
