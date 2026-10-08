"""Score the holdout: which signal ranked the next twelve months best, and does the agent team
add anything once the scorecard is known?

Every company's return runs twelve months from the first month-end on or after its filing,
and is compared with SPY over the same window and with the median company in the sample.
All companies share roughly the same year, so this is one cross-section: the confidence
intervals (bootstrap over companies) cover company noise, not a different market regime.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np

from backtest.analyze import spearman
from ddagent.prices import Prices

from .run import ORD, RESULTS, RUNS

SIGNALS = {
    "scorecard": ("Scorecard (code only)", lambda r: r["scorecard"]["pct"]),
    "single": ("Single prompt: verdict", lambda r: ORD.get(r["single"].get("verdict"))),
    "single_conv": ("Single prompt: conviction 1-5", lambda r: r["single"].get("conviction")),
    "team_pm": ("Agent team: PM verdict", lambda r: ORD.get(r.get("team", {}).get("pm_verdict"))),
    "team_score": ("Agent team: scorecard incl. red-team penalty", lambda r: r.get("team", {}).get("scorecard_with_penalty")),
}


def window(series, filed: str, months: int = 12):
    """(total return, max drawdown) over `months` from the first month-end >= filed; None if incomplete."""
    if not series:
        return None
    i0 = next((i for i, m in enumerate(series.months) if m >= filed), None)
    if i0 is None or i0 + months >= len(series.months):
        return None
    path = series.adjclose[i0: i0 + months + 1]
    peak, mdd = path[0], 0.0
    for p in path:
        peak = max(peak, p)
        mdd = min(mdd, p / peak - 1)
    return path[-1] / path[0] - 1, mdd


def attach_outcomes(rows: list[dict], prices, months: int = 12, refresh: bool = False) -> list[dict]:
    spy = prices.monthly("SPY", refresh=refresh)
    out = []
    for r in rows:
        w = window(prices.monthly(r["ticker"], refresh=refresh), r["filed"], months)
        b = window(spy, r["filed"], months)
        if not w or not b:
            continue
        out.append({**r, "ret": w[0], "mdd": w[1], "spy": b[0], "excess": w[0] - b[0]})
    med = float(np.median([r["ret"] for r in out])) if out else 0.0
    for r in out:
        r["beat_median"] = r["ret"] > med
    return out


def boot_ic(x: list[float], y: list[float], n: int = 2000, seed: int = 11) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    x, y = np.asarray(x, float), np.asarray(y, float)
    ic = spearman(list(x), list(y))
    draws = []
    for _ in range(n):
        idx = rng.integers(0, len(x), len(x))
        if len(set(x[idx])) > 1:
            draws.append(spearman(list(x[idx]), list(y[idx])))
    if not draws:
        return ic, float("nan"), float("nan")
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return ic, float(lo), float(hi)


def ols_hc1(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    n, k = X.shape
    inv = np.linalg.inv(X.T @ X)
    V = inv @ (X.T * e ** 2) @ X @ inv * n / (n - k)
    return beta, beta / np.sqrt(np.diag(V))


def winsor(v: np.ndarray, p: float = 1.0) -> np.ndarray:
    lo, hi = np.percentile(v, [p, 100 - p])
    return np.clip(v, lo, hi)


def analyze(rows: list[dict], months: int = 12) -> dict:
    res: dict = {"n": len(rows), "months": months, "filed": [min(r["filed"] for r in rows), max(r["filed"] for r in rows)],
                 "spy": float(np.median([r["spy"] for r in rows])),
                 "median_return": float(np.median([r["ret"] for r in rows])), "signals": {}}
    for key, (label, f) in SIGNALS.items():
        pts = [(f(r), r["ret"]) for r in rows if f(r) is not None]
        if len(pts) < 20 or len({p[0] for p in pts}) < 2:  # a constant signal ranks nothing
            continue
        ic, lo, hi = boot_ic([p[0] for p in pts], [p[1] for p in pts])
        res["signals"][key] = {"label": label, "n": len(pts), "ic": ic, "ci": [lo, hi]}

    def buckets(get):
        out = {}
        for v in ("Dig deeper", "Watch", "Pass"):
            g = [r for r in rows if get(r) == v]
            if g:
                out[v] = {"n": len(g), "median_excess": float(np.median([r["excess"] for r in g])),
                          "median_ret": float(np.median([r["ret"] for r in g])),
                          "beat_median": float(np.mean([r["beat_median"] for r in g]))}
        return out

    res["buckets"] = {"scorecard": buckets(lambda r: r["scorecard"]["verdict"]),
                      "single": buckets(lambda r: r["single"].get("verdict")),
                      "team_pm": buckets(lambda r: r.get("team", {}).get("pm_verdict"))}

    # Does the model add anything once the scorecard is known?
    inc = {}
    for key, get in (("team_pm", lambda r: ORD.get(r.get("team", {}).get("pm_verdict"))),
                     ("single", lambda r: ORD.get(r["single"].get("verdict")))):
        rs = [r for r in rows if get(r) is not None]
        if len(rs) < 30 or len({get(r) for r in rs}) < 2:  # a constant verdict can't be regressed on
            continue
        y = winsor(np.array([r["excess"] for r in rs]))
        X = np.column_stack([np.ones(len(rs)), [r["scorecard"]["pct"] for r in rs], [get(r) for r in rs]])
        b, t = ols_hc1(y, X)
        inc[key] = {"n": len(rs), "scorecard_beta": float(b[1]), "scorecard_t": float(t[1]),
                    "model_beta": float(b[2]), "model_t": float(t[2])}
    res["incremental"] = inc

    # When the PM and the scorecard disagree, who was right? (Watch calls are not scored.)
    def right(v, r):
        return r["beat_median"] if v == "Dig deeper" else (not r["beat_median"]) if v == "Pass" else None

    dis = [r for r in rows if r.get("team", {}).get("pm_verdict") and r["team"]["pm_verdict"] != r["scorecard"]["verdict"]]
    pm = [right(r["team"]["pm_verdict"], r) for r in dis]
    sc = [right(r["scorecard"]["verdict"], r) for r in dis]
    res["disagreements"] = {"n": len(dis), "pm_right": sum(1 for x in pm if x), "pm_scored": sum(1 for x in pm if x is not None),
                            "scorecard_right": sum(1 for x in sc if x), "scorecard_scored": sum(1 for x in sc if x is not None)}

    # Do red-team red flags predict drawdowns?
    rt = [r for r in rows if "high_objections" in r.get("team", {})]
    if len(rt) >= 20:
        flagged = [r for r in rt if r["team"]["high_objections"] >= 2]
        clean = [r for r in rt if r["team"]["high_objections"] == 0]
        res["red_flags"] = {
            "ic_vs_drawdown": spearman([-r["team"]["high_objections"] for r in rt], [r["mdd"] for r in rt]),
            "flagged_n": len(flagged), "clean_n": len(clean),
            "flagged_dd30": float(np.mean([r["mdd"] <= -0.30 for r in flagged])) if flagged else None,
            "clean_dd30": float(np.mean([r["mdd"] <= -0.30 for r in clean])) if clean else None}

    calls = [r for r in rows if r.get("calls")]
    res["cost"] = {"tokens_in": sum(r["tokens"][0] for r in calls), "tokens_out": sum(r["tokens"][1] for r in calls)}
    return res


def _pct(x, d=0):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * 100:.{d}f}%"


HEADER = """# Holdout: does the agent team add anything the scorecard doesn't?

Generated {today} by `python -m holdout analyze`. Model: Claude Sonnet 4.5, whose training data ends July 2025.
Sample: US-listed non-financial companies worth at least $300M that filed a 10-K after that cutoff; the
hypotheses, outcomes and decision rules were fixed in advance in `holdout/PREREGISTRATION.md`. The model
never saw these filings or what followed, and web research is off, so nothing after the filing reaches it.
"""


def report(res: dict, top: bool = True) -> str:
    h = {6: "six", 12: "twelve"}.get(res["months"], str(res["months"]))
    L = ([HEADER.format(today=date.today().isoformat())] if top else []) + [
         f"### {h.capitalize()}-month returns: {res['n']} companies (10-Ks filed {res['filed'][0]} to {res['filed'][1]})", "",
         f"Median company return: {_pct(res['median_return'], 1)}; SPY over the median window: {_pct(res['spy'], 1)}.", "",
         f"#### Which signal ranked the next {h} months best?", "",
         f"| Signal | Companies | Rank correlation with {res['months']}-month return | 95% CI |", "|---|---|---|---|"]
    for s in res["signals"].values():
        L.append(f"| {s['label']} | {s['n']} | {s['ic']:.3f} | {s['ci'][0]:.3f} to {s['ci'][1]:.3f} |")
    L += ["", "#### By verdict", "", "| Signal | Verdict | Companies | Beat the median | Median return vs SPY |", "|---|---|---|---|---|"]
    names = {"scorecard": "Scorecard", "single": "Single prompt", "team_pm": "Agent team (PM)"}
    for key, b in res["buckets"].items():
        for v, d in b.items():
            L.append(f"| {names[key]} | {v} | {d['n']} | {_pct(d['beat_median'])} | {_pct(d['median_excess'], 1)} |")
    if res["incremental"]:
        L += ["", "#### Does the model add anything beyond the scorecard?", "",
              "Return vs SPY (winsorized 1%) regressed on the scorecard and the model's verdict (0 Pass, 1 Watch, 2 Dig deeper); robust t-statistics.", "",
              "| Model signal | Companies | Scorecard coefficient (t) | Model verdict coefficient (t) |", "|---|---|---|---|"]
        for key, d in res["incremental"].items():
            L.append(f"| {names[key]} | {d['n']} | {d['scorecard_beta']:.3f} ({d['scorecard_t']:.1f}) | "
                     f"{d['model_beta'] * 100:.1f} pts per step ({d['model_t']:.1f}) |")
    d = res["disagreements"]
    L += ["", "#### When the PM and the scorecard disagreed", "",
          f"{d['n']} disagreements. Scored where the call was Dig deeper (right if it beat the median) or Pass (right if it trailed): "
          f"PM right {d['pm_right']}/{d['pm_scored']}, scorecard right {d['scorecard_right']}/{d['scorecard_scored']}."]
    if "red_flags" in res:
        f = res["red_flags"]
        L += ["", "#### Do red-team red flags predict drawdowns?", "",
              f"Rank correlation between fewer high-severity objections and a smaller drawdown over the window: {f['ic_vs_drawdown']:.3f}. "
              f"Companies with two or more high-severity objections fell 30%+ from a peak {_pct(f['flagged_dd30'])} of the time "
              f"(n = {f['flagged_n']}), against {_pct(f['clean_dd30'])} for companies with none (n = {f['clean_n']})."]
    return "\n".join(L) + "\n"


LIMITS = """## Limits

- One period: every company's window falls between late 2025 and September 2026, so a single market regime drives the result.
- A few hundred companies detect only a moderate effect; the confidence intervals show how wide the uncertainty is.
- The twelve-month group is small and tilted to June fiscal years (August-September filers).
- Web research is off in this test; the live tool uses it.
"""


def main(runs_path: Path = RUNS, refresh: bool = False, dev_path: Path | None = None) -> int:
    from backtest.data import _ua

    from ddagent.edgar import Edgar

    from . import fundamentals, outcomes

    raw = [json.loads(l) for l in runs_path.read_text().splitlines() if l.strip()]
    edgar = Edgar(_ua(), cache_dir=outcomes.SNAPSHOT_CACHE)
    snap = outcomes.SNAPSHOT_CACHE / "SNAPSHOT_DATE"
    if not snap.exists():
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(date.today().isoformat())

    results: dict = {"facts_snapshot": snap.read_text().strip()}
    text = [HEADER.format(today=date.today().isoformat())]
    fund_rows = outcomes.attach(raw, edgar)
    dev = []
    if dev_path and dev_path.exists() and dev_path != runs_path:
        dev = outcomes.attach([json.loads(l) for l in dev_path.read_text().splitlines() if l.strip()], edgar)
    if len(fund_rows) >= 20:
        results["fundamentals"] = fundamentals.analyze(fund_rows, dev)
        text.append(fundamentals.report(results["fundamentals"]))

    prices = Prices(".cache/backtest/prices")
    text.append("## Secondary: stock returns (low statistical power; see PREREGISTRATION.md)\n")
    for months in (6, 12):
        rows = attach_outcomes(raw, prices, months, refresh=refresh and months == 6)
        if len(rows) < 30:
            continue
        res = analyze(rows, months)
        results[f"returns_{months}m"] = res
        text.append(report(res, top=False))
    if len(results) == 1:
        raise SystemExit("not enough completed runs with observable outcomes yet")
    md = "\n".join(text) + "\n" + LIMITS
    out = runs_path.parent
    stem = runs_path.stem.replace("runs_", "")
    (out / f"summary_{stem}.json").write_text(json.dumps(results, indent=2, default=str))
    (out / f"RESULTS_{stem}.md").write_text(md)
    print(md)
    return 0
