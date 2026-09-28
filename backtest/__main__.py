"""python -m backtest: download data, score every company point-in-time, test the verdicts.

Steps are cached, so a rerun after an interruption picks up where it stopped.
Outputs (committed): backtest/results/RESULTS.md, summary.json, peers.json, panel.csv.gz, *.png
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from datetime import date
from pathlib import Path

from ddagent.cli import load_dotenv

from . import analyze, data, panel

OUT = Path("backtest/results")


def pct(x, d=1):
    return "n/a" if x is None else f"{x * 100:.{d}f}%"


def report(res: dict, peers_as_of: str) -> str:
    u = res["universe"]
    f0, f1 = u["formations"][0], u["formations"][-1]
    lines = [
        "# Does the scorecard predict anything?",
        "",
        f"Point-in-time backtest of the scorecard, generated {date.today().isoformat()} by `python -m backtest`.",
        "",
        f"Every June 30 from {f0[:4]} to {f1[:4]}, each US-listed non-financial company worth at least "
        f"${analyze.MIN_MCAP / 1e6:,.0f}M was scored with the same code the memos use, on only the 10-K data "
        "public that day, and grouped by verdict. Portfolios are held twelve months. "
        f"{u['rows']:,} company-years, {u['companies']:,} companies. No model is involved: the red-team penalty is zero.",
        "",
    ]
    for key, title in (("abs_verdict", "Absolute rubric (one threshold for every industry)"),
                       ("rel_verdict", "Sector-relative rubric (scored against industry peers)")):
        r = res[key]
        lines += [f"## {title}", "", "| | Dig deeper | Watch | Pass |", "|---|---|---|---|"]
        for wt, lab in (("ew", "Return, equal-weighted (annualized)"), ("vw", "Return, value-weighted (annualized)")):
            b = r[wt]["buckets"]
            lines.append(f"| {lab} | " + " | ".join(pct(b.get(v, {}).get("annualized")) for v in analyze.VERDICTS) + " |")
        lines.append("| Beat the median stock next 12 months | " +
                     " | ".join(pct(r["beat_median"][v], 0) for v in analyze.VERDICTS) + " |")
        lines.append("| Names per year (avg) | " + " | ".join(f"{r['avg_names'][v]:.0f}" for v in analyze.VERDICTS) + " |")
        lines += ["", "| Dig deeper minus Pass | Equal-weighted | Value-weighted |", "|---|---|---|"]
        e, v = r["ew"]["long_short"], r["vw"]["long_short"]
        lines.append(f"| Spread, annualized (t) | {pct(e['annualized'])} ({e['t_mean']:.1f}) | {pct(v['annualized'])} ({v['t_mean']:.1f}) |")
        lines.append(f"| Alpha after FF5 + momentum, annualized (t) | {pct(e['alpha_annualized'])} ({e['t_alpha']:.1f}) | "
                     f"{pct(v['alpha_annualized'])} ({v['t_alpha']:.1f}) |")
        for fac in ("RMW", "HML", "SMB", "Mom"):
            lines.append(f"| Loading on {fac} (t) | {e['loadings'][fac]['beta']:.2f} ({e['loadings'][fac]['t']:.1f}) | "
                         f"{v['loadings'][fac]['beta']:.2f} ({v['loadings'][fac]['t']:.1f}) |")
        ic = r["ic"]
        lines += ["", f"Rank correlation of the score with the next 12 months' return: mean {ic['mean']:.3f} "
                      f"(t = {ic['t']:.1f}), positive in {ic['positive_years']} of {ic['years']} years.", ""]
    s = res["survivorship"]
    a, b = s["listed today"], s["no longer listed (sample)"]
    lines += [
        "## Caveats",
        "",
        "- **Survivorship.** Prices come from today's listings, so companies that were later acquired or went "
        "bankrupt are missing. Their fundamentals are not: scored on the dimensions that need no price, "
        f"{pct(b['pass_share'], 0)} of a sample of no-longer-listed company-years would have been Pass, against "
        f"{pct(a['pass_share'], 0)} for companies still listed. "
        + ("Because the missing names skew toward Pass, and many of them failed, their absence most likely makes "
           "Pass look better than it was, which works against the spread above."
           if (b["pass_share"] or 0) > (a["pass_share"] or 0) else
           "The missing names do not skew toward Pass, so the direction of this bias is unclear."),
        "- **Thresholds were set before this test** (v0.2) and not tuned on it. The sector-relative cut-offs "
        "(top, middle, bottom third) are the obvious default, not fitted.",
        "- **Market cap** is cover-page shares outstanding times the price quoted at formation. "
        "Microcaps under the size floor and financials (SIC 6000-6799) are excluded.",
        "- **Costs** are ignored; turnover is annual, so they are small relative to the spreads.",
        "- The red-team penalty and the PM's view are not tested here. The verdict ledger "
        "(`ddagent-grade`) tracks them going forward.",
        "",
        f"Peer tables for live memos (`peers.json`) come from the {peers_as_of[:4]} formation.",
    ]
    return "\n".join(lines) + "\n"


def chart(res: dict, path: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    for key, lab, style in (("abs_verdict", "Absolute", "-"), ("rel_verdict", "Sector-relative", "--")):
        ls = res[key]["ew"]["_ls_series"]
        months = sorted(ls)
        g, ys = 1.0, []
        for m in months:
            g *= 1 + ls[m]
            ys.append(g)
        ax.plot(range(len(ys)), ys, style, label=f"{lab}: Dig deeper minus Pass (EW)")
    ticks = [i for i, m in enumerate(months) if m.endswith("-07")][::2]
    ax.set_xticks(ticks, [months[i][:4] for i in ticks])
    ax.axhline(1, color="grey", lw=0.6)
    ax.set_ylabel("Growth of $1")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def summary(res: dict) -> dict:
    out = {"generated": date.today().isoformat(), "formations": [res["universe"]["formations"][0][:4],
                                                                  res["universe"]["formations"][-1][:4]],
           "company_years": res["universe"]["rows"]}
    for key in ("abs_verdict", "rel_verdict"):
        r = res[key]
        out[key] = {"annualized_ew": {v: r["ew"]["buckets"].get(v, {}).get("annualized") for v in analyze.VERDICTS},
                    "beat_median": r["beat_median"],
                    "spread_alpha_ew": r["ew"]["long_short"]["alpha_annualized"],
                    "spread_alpha_t_ew": r["ew"]["long_short"]["t_alpha"],
                    "ic_mean": r["ic"]["mean"]}
    return out


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="python -m backtest", description=__doc__)
    ap.add_argument("--first", type=int, default=2012)
    ap.add_argument("--last", type=int, default=2025, help="last formation year with 12 months of returns")
    ap.add_argument("--delisted-sample", type=int, default=3000)
    ap.add_argument("--limit", type=int, default=None,
                    help="smoke test: score only the first N listed companies (results go to .cache, not backtest/results)")
    args = ap.parse_args(argv)

    global OUT
    if args.limit:
        OUT = data.CACHE / "smoke"
    OUT.mkdir(parents=True, exist_ok=True)
    print("1/5 SEC company facts (about 1.3 GB, once)", file=sys.stderr)
    zpath = data.companyfacts_zip()
    listed = data.listed_tickers()
    print("2/5 factors", file=sys.stderr)
    ff = data.factors()
    prices = data.Prices(data.CACHE / "prices")

    print("3/5 scoring every company at every June 30 (fetches prices as needed)", file=sys.stderr)
    panel_path = data.CACHE / ("panel.json" if not args.limit else f"panel_smoke_{args.limit}.json")
    if panel_path.exists():
        rows = json.loads(panel_path.read_text())
    else:
        rows = panel.build(zpath, listed, range(args.first, args.last + 2), prices, args.delisted_sample,
                           limit=args.limit)
        panel_path.write_text(json.dumps(rows))

    # Panels built before the cik fix: recover the CIK from the ticker, drop what can't be matched.
    by_ticker = {v["ticker"]: c for c, v in listed.items()}
    for r in rows:
        if r.get("cik") is None:
            r["cik"] = by_ticker.get(r.get("ticker"), -1)
    rows = [r for r in rows if r["cik"] != -1 or not r.get("listed_today")]

    print("4/5 industry codes", file=sys.stderr)
    sic = data.sic_codes(sorted({int(r["cik"]) for r in rows if r.get("listed_today") and r.get("mcap")}))

    print("5/5 portfolios and regressions", file=sys.stderr)
    res = analyze.run(rows, sic, prices, ff, last_formation=f"{args.last}-06-30")
    peers_as_of = analyze.write_peers(res["_universe_all"], OUT / "peers.json")
    (OUT / "RESULTS.md").write_text(report(res, peers_as_of))
    (OUT / "summary.json").write_text(json.dumps(summary(res), indent=2))
    chart(res, OUT / "spread.png")
    cols = ["cik", "ticker", "name", "formed", "filed", "fy_end", "revenue", "mcap", "sic", "abs_pct", "abs_verdict",
            "rel_group", "rel_pct", "rel_verdict", "fwd_12m"]
    with gzip.open(OUT / "panel.csv.gz", "wt", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in res["_tested"]:
            w.writerow(r)
    print((OUT / "RESULTS.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
