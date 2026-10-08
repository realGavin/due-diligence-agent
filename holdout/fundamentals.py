"""Primary analysis (PREREGISTRATION.md): do the model's judgments predict what happened to the
business, beyond what the code-only scorecard already knew?"""
from __future__ import annotations

import numpy as np

from backtest.analyze import spearman

from .analyze import boot_ic, ols_hc1
from .run import ORD

# Higher = better expected business. Red-team flags are negated so every signal points the same way.
SIGNALS = {
    "scorecard": ("Scorecard (code only)", lambda r: r["scorecard"]["pct"]),
    "single_score": ("Single prompt: score 0-100", lambda r: r["single"].get("score")),
    "team_score": ("Agent team: PM score 0-100", lambda r: r.get("team", {}).get("score")),
    "single": ("Single prompt: verdict", lambda r: ORD.get(r["single"].get("verdict"))),
    "team_pm": ("Agent team: PM verdict", lambda r: ORD.get(r.get("team", {}).get("pm_verdict"))),
    "red_flags": ("Agent team: high-severity red-team objections (fewer = better)",
                  lambda r: -r["team"]["high_objections"] if "high_objections" in r.get("team", {}) else None),
}
OUTCOMES = {"margin_change": "Operating margin change (pts)", "growth_change": "Revenue growth change (pts)"}


def pct_rank(v) -> np.ndarray:
    """Average ranks scaled to 0-1 (ties share a rank)."""
    v = np.asarray(v, float)
    order = v.argsort(kind="mergesort")
    r = np.empty(len(v))
    r[order] = np.arange(len(v))
    for x in np.unique(v):
        m = v == x
        r[m] = r[m].mean()
    return r / max(len(v) - 1, 1)


def auc(score: list[float], bad: list[bool], n_boot: int = 2000, seed: int = 5) -> tuple[float, float, float] | None:
    """P(a deteriorating company scored lower than a healthy one); 0.5 = no information."""
    s, b = np.asarray(score, float), np.asarray(bad, bool)
    if b.sum() < 5 or (~b).sum() < 5:
        return None

    def one(si, bi):
        pos, neg = si[bi], si[~bi]
        if not len(pos) or not len(neg):
            return np.nan
        diff = neg[:, None] - pos[None, :]
        return float(((diff > 0) + 0.5 * (diff == 0)).mean())

    rng = np.random.default_rng(seed)
    draws = [one(s[i], b[i]) for i in (rng.integers(0, len(s), len(s)) for _ in range(n_boot))]
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return one(s, b), float(lo), float(hi)


def forecast_change(fc: dict | None, r: dict, key: str) -> float | None:
    """Forecast change vs the filed year: forecast growth minus filed growth, or forecast margin
    minus filed margin, in points."""
    fc = fc or {}
    if key == "margin_change":
        f, base = fc.get("operating_margin_pct"), r["metrics"].get("op_margin")
    else:
        f, base = fc.get("revenue_growth_pct"), r["metrics"].get("growth")
    return None if f is None or base is None or abs(base) >= 1e17 else f - base


def direction(change: float | None, key: str) -> str | None:
    if change is None:
        return None
    band = 1.0 if key == "margin_change" else 2.0
    if key == "margin_change":
        return "expand" if change > band else "compress" if change < -band else "stable"
    return "accelerate" if change > band else "decelerate" if change < -band else "stable"


def baselines(dev: list[dict]) -> dict:
    """Simple forecasting rules fitted on the dev split only (never on test)."""
    def majority(key):
        vals = [r["realized"][key] for r in dev if key in r["realized"]]
        return max(set(vals), key=vals.count) if vals else "stable"

    g = [r["metrics"].get("growth") for r in dev if r["metrics"].get("growth") is not None]
    m = [r["metrics"].get("op_margin") for r in dev if r["metrics"].get("op_margin") is not None]
    return {"majority": {"revenue_growth": majority("revenue_growth"), "operating_margin": majority("operating_margin")},
            "median_growth": float(np.median(g)) if g else 0.0, "median_margin": float(np.median(m)) if m else 0.0}


def reversion(r: dict, b: dict, key: str) -> float | None:
    """Mean-reversion forecast of the change: the further above the dev median, the bigger the fall."""
    if key == "margin_change":
        m = r["metrics"].get("op_margin")
        return None if m is None or abs(m) >= 1e17 else b["median_margin"] - m
    g = r["metrics"].get("growth")
    return None if g is None or abs(g) >= 1e17 else b["median_growth"] - g


def boot_ic_diff(x1, x2, y, n=2000, seed=13):
    """IC(x1, y) - IC(x2, y) with a paired bootstrap interval."""
    x1, x2, y = (np.asarray(v, float) for v in (x1, x2, y))
    d0 = spearman(list(x1), list(y)) - spearman(list(x2), list(y))
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if len(set(x1[i])) > 1 and len(set(x2[i])) > 1:
            draws.append(spearman(list(x1[i]), list(y[i])) - spearman(list(x2[i]), list(y[i])))
    lo, hi = np.percentile(draws, [2.5, 97.5]) if draws else (float("nan"), float("nan"))
    return float(d0), float(lo), float(hi)


FORECASTERS = {"Agent team (PM)": lambda r: r.get("team", {}).get("forecast"),
               "Single prompt": lambda r: r["single"].get("forecast")}
DIR_KEY = {"margin_change": "operating_margin", "growth_change": "revenue_growth"}


def forecast_tests(rows: list[dict], b: dict, n_boot: int = 2000, seed: int = 9) -> dict:
    """H3 and secondaries: does the forecast change rank the realized change, better than mean
    reversion? Plus direction accuracy against the baselines."""
    out = {}
    for key in ("margin_change", "growth_change"):
        rs = [r for r in rows if key in r["fund"] and reversion(r, b, key) is not None]
        if len(rs) < 20:
            continue
        y = [r["fund"][key] for r in rs]
        base = [reversion(r, b, key) for r in rs]
        res = {"Baseline: mean reversion": {"ic": spearman(base, y)}}
        dkey = DIR_KEY[key]
        truth = [r["realized"].get(dkey) for r in rs]
        base_acc = {"Baseline: most common outcome in dev": np.mean([b["majority"][dkey] == t for t in truth]),
                    "Baseline: mean reversion": np.mean([direction(v, key) == t for v, t in zip(base, truth)])}
        res["Baseline: mean reversion"]["accuracy"] = float(base_acc["Baseline: mean reversion"])
        res["Baseline: most common outcome in dev"] = {"accuracy": float(base_acc["Baseline: most common outcome in dev"])}
        for name, get in FORECASTERS.items():
            pts = [(forecast_change(get(r), r, key), bv, yv, t) for r, bv, yv, t in zip(rs, base, y, truth)]
            pts = [p for p in pts if p[0] is not None]
            if len(pts) < 20 or len({p[0] for p in pts}) < 2:
                continue
            ic, lo, hi = boot_ic([p[0] for p in pts], [p[2] for p in pts])
            d, dlo, dhi = boot_ic_diff([p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts])
            acc = float(np.mean([direction(p[0], key) == p[3] for p in pts]))
            res[name] = {"n": len(pts), "ic": ic, "ci": [lo, hi], "vs_reversion": d, "vs_ci": [dlo, dhi], "accuracy": acc}
        out[key] = {"n": len(rs), "results": res}
    return out


def analyze(rows: list[dict], dev: list[dict]) -> dict:
    res: dict = {"n": len(rows), "ic": {}, "auc": {}, "incremental": {}}
    for okey in OUTCOMES:
        res["ic"][okey] = {}
        for skey, (label, f) in SIGNALS.items():
            pts = [(f(r), r["fund"][okey]) for r in rows if f(r) is not None and okey in r["fund"]]
            if len(pts) >= 20 and len({p[0] for p in pts}) > 1:
                ic, lo, hi = boot_ic([p[0] for p in pts], [p[1] for p in pts])
                res["ic"][okey][skey] = {"label": label, "n": len(pts), "ic": ic, "ci": [lo, hi]}
    for skey, (label, f) in SIGNALS.items():
        pts = [(f(r), r["fund"]["deteriorated"]) for r in rows if f(r) is not None and "deteriorated" in r["fund"]]
        a = auc([p[0] for p in pts], [p[1] for p in pts]) if len({p[0] for p in pts}) > 1 else None
        if a:
            res["auc"][skey] = {"label": label, "n": len(pts), "auc": a[0], "ci": [a[1], a[2]],
                                "base_rate": float(np.mean([p[1] for p in pts]))}

    # H1/H2: the model's signal, controlling for the scorecard.
    for okey, kind in (("margin_change", "pts"), ("deteriorated", "probability")):
        for skey in ("team_score", "red_flags", "single_score", "team_pm"):
            f = SIGNALS[skey][1]
            rs = [r for r in rows if f(r) is not None and okey in r["fund"]]
            if len(rs) < 30 or len({f(r) for r in rs}) < 2:
                continue
            # Ranks, not raw values: pre-revenue companies have margin changes of hundreds or
            # thousands of points, which would otherwise decide the coefficient on their own.
            y = np.array([float(r["fund"][okey]) for r in rs])
            y = pct_rank(y) if kind == "pts" else y
            X = np.column_stack([np.ones(len(rs)), pct_rank([r["scorecard"]["pct"] for r in rs]), pct_rank([f(r) for r in rs])])
            beta, t = ols_hc1(y, X)
            res["incremental"][f"{okey}:{skey}"] = {"outcome": okey, "signal": SIGNALS[skey][0], "n": len(rs),
                                                    "beta": float(beta[2]), "t": float(t[2]),
                                                    "scorecard_t": float(t[1])}
    res["forecasts"] = forecast_tests(rows, baselines(dev or rows))
    res["baselines_from"] = "dev split" if dev else "same rows (no dev split available)"
    return res


def report(res: dict) -> str:
    L = [f"## Primary: what happened to the business ({res['n']} companies)", "",
         "Outcomes from the company's next two quarterly reports, each against the same quarter a year earlier "
         "(see `holdout/outcomes.py`). A deterioration is a margin drop of 3+ points or a growth slowdown of 10+ points.", ""]
    for okey, olabel in OUTCOMES.items():
        if not res["ic"].get(okey):
            continue
        L += [f"### {olabel}: rank correlation with each signal", "", "| Signal | Companies | Rank correlation | 95% CI |", "|---|---|---|---|"]
        for s in res["ic"][okey].values():
            L.append(f"| {s['label']} | {s['n']} | {s['ic']:.3f} | {s['ci'][0]:.3f} to {s['ci'][1]:.3f} |")
        L.append("")
    if res["auc"]:
        base = next(iter(res["auc"].values()))["base_rate"]
        L += [f"### Spotting deterioration (base rate {base * 100:.0f}%)", "",
              "AUC: the chance a deteriorating company got a worse signal than a healthy one. 0.50 = no information.", "",
              "| Signal | Companies | AUC | 95% CI |", "|---|---|---|---|"]
        for s in res["auc"].values():
            L.append(f"| {s['label']} | {s['n']} | {s['auc']:.3f} | {s['ci'][0]:.3f} to {s['ci'][1]:.3f} |")
        L.append("")
    if res["incremental"]:
        L += ["### Beyond the scorecard (H1, H2)", "",
              "Outcome regressed on the scorecard and one model signal, both as percentile ranks (0-1); margin change "
              "also as a percentile rank, deterioration as 0/1. Robust t-statistics. A coefficient of 0.2 on margin change "
              "means going from the lowest to the highest signal moves a company 20 percentiles up the margin-change ranking. "
              "The hypothesis holds if the model signal's t is above 1.96 in the predicted direction.", "",
              "| Outcome | Model signal | Companies | Model coefficient (t) | Scorecard t |", "|---|---|---|---|---|"]
        for d in res["incremental"].values():
            L.append(f"| {d['outcome']} | {d['signal']} | {d['n']} | {d['beta']:.3f} ({d['t']:.1f}) | {d['scorecard_t']:.1f} |")
        L.append("")
    for key, f in res["forecasts"].items():
        label = {"margin_change": "Operating margin", "growth_change": "Revenue growth"}[key]
        L += [f"### {label} forecasts ({'H3' if key == 'margin_change' else 'secondary'}; {f['n']} companies)", "",
              "The forecast change (next-year forecast minus the filed year) ranked against the realized change, "
              f"compared with mean reversion fitted on the {res['baselines_from']}. Direction accuracy uses the "
              "same bands as the outcomes (margin ±1 point, growth ±2 points).", "",
              "| Forecaster | Rank correlation (95% CI) | vs mean reversion (95% CI) | Direction accuracy |", "|---|---|---|---|"]
        for name, e in f["results"].items():
            ic = f"{e['ic']:.3f} ({e['ci'][0]:.3f} to {e['ci'][1]:.3f})" if "ci" in e else (f"{e['ic']:.3f}" if "ic" in e else "")
            vs = f"{e['vs_reversion']:+.3f} ({e['vs_ci'][0]:+.3f} to {e['vs_ci'][1]:+.3f})" if "vs_ci" in e else ""
            L.append(f"| {name} | {ic} | {vs} | {e['accuracy'] * 100:.0f}% |")
        L.append("")
    return "\n".join(L)
