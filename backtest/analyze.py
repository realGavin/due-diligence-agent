"""Turn the scored panel into evidence: do the verdicts predict anything?

Portfolios are formed every June 30 from that day's verdicts and held twelve months
(July through June), buy-and-hold, equal- and value-weighted. The headline test is the
Dig deeper minus Pass spread, and whether it survives the Fama-French five factors plus
momentum (i.e. whether the rubric is more than known quality/value/size exposure).
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from ddagent.prices import Prices, Series
from ddagent.scorecard import RELATIVE_DIMS, group_keys, pick_group, score_relative

VERDICTS = ["Dig deeper", "Watch", "Pass"]
MIN_MCAP = 300e6
MIN_PEERS = 15


# ----------------------------------------------------------------------------- universe

def is_financial(sic: int) -> bool:
    return 6000 <= sic <= 6799


def universe(rows: list[dict], sic: dict[int, int]) -> list[dict]:
    out = []
    for r in rows:
        code = sic.get(int(r["cik"]), 0)
        if not r.get("listed_today") or not r.get("mcap") or r["mcap"] < MIN_MCAP or is_financial(code):
            continue
        out.append({**r, "sic": code})
    return out


# ----------------------------------------------------------------------------- relative scores

METRIC_KEYS = sorted({k for keys in RELATIVE_DIMS.values() for k, _ in keys})


def _metric(r: dict, k: str) -> float | None:
    v = r.get(f"m_{k}")
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return math.inf if v >= 1e18 else -math.inf if v <= -1e18 else float(v)


def peer_tables(rows: list[dict]) -> dict[str, dict[str, list[float]]]:
    """group -> metric -> sorted values, for SIC 2-digit industries, divisions and 'All'."""
    groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for k in METRIC_KEYS:
            v = _metric(r, k)
            if v is not None:
                for g in group_keys(r["sic"]):
                    groups[g][k].append(v)
    return {g: {k: sorted(v) for k, v in d.items()} for g, d in groups.items()}


def add_relative(rows: list[dict]) -> None:
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["formed"]].append(r)
    for yr_rows in by_year.values():
        tables = peer_tables(yr_rows)
        for r in yr_rows:
            g = pick_group(r["sic"], tables, MIN_PEERS)
            m = {k: _metric(r, k) for k in METRIC_KEYS if _metric(r, k) is not None}
            sc = score_relative(m, tables[g], g, min_peers=MIN_PEERS)
            r["rel_group"], r["rel_pct"], r["rel_verdict"] = g, round(sc.pct, 4), sc.verdict


# ----------------------------------------------------------------------------- returns

def month_returns(s: Series, start: str, n: int = 12) -> list[float | None]:
    """Monthly total returns for the n months after `start` (a month-end date).
    None once the price history ends (treated as cash in portfolios)."""
    i0 = s.index_at(start)
    if i0 is None or s.months[i0][:7] != start[:7]:
        return [None] * n
    out = []
    for k in range(1, n + 1):
        i = i0 + k
        out.append(s.adjclose[i] / s.adjclose[i - 1] - 1 if i < len(s.adjclose) else None)
    return out


def next_months(start: str, n: int = 12) -> list[str]:
    y, m = int(start[:4]), int(start[5:7])
    out = []
    for _ in range(n):
        m += 1
        if m == 13:
            y, m = y + 1, 1
        out.append(f"{y}-{m:02d}")
    return out


def portfolio(members: list[tuple[float, list[float | None]]]) -> list[float]:
    """Buy-and-hold monthly returns of a portfolio: members = (initial weight, monthly returns)."""
    w = [x[0] for x in members]
    out = []
    for t in range(12):
        tot = sum(w)
        if tot <= 0:
            out.append(0.0)
            continue
        ret = 0.0
        for j, (_, rets) in enumerate(members):
            r = rets[t] if rets[t] is not None else 0.0
            ret += w[j] / tot * r
            w[j] *= 1 + r
        out.append(ret)
    return out


def bucket_series(rows: list[dict], prices: Prices, key: str, weighting: str) -> dict[str, dict[str, float]]:
    """verdict -> {YYYY-MM: return}."""
    out: dict[str, dict[str, float]] = {v: {} for v in VERDICTS}
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["formed"]].append(r)
    for formed, yr_rows in sorted(by_year.items()):
        months = next_months(formed)
        for v in VERDICTS:
            members = []
            for r in yr_rows:
                if r[key] != v:
                    continue
                rets = r["_rets"]
                if all(x is None for x in rets):
                    continue
                members.append((r["mcap"] if weighting == "vw" else 1.0, rets))
            if members:
                for ym, x in zip(months, portfolio(members)):
                    out[v][ym] = x
    return out


# ----------------------------------------------------------------------------- statistics

def ols_nw(y: np.ndarray, X: np.ndarray, lags: int = 6) -> tuple[np.ndarray, np.ndarray]:
    """OLS coefficients and Newey-West t-stats."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    n = len(y)
    xe = X * e[:, None]
    S = xe.T @ xe
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = xe[L:].T @ xe[:-L]
        S += w * (G + G.T)
    XtX_inv = np.linalg.inv(X.T @ X)
    V = XtX_inv @ S @ XtX_inv
    return beta, beta / np.sqrt(np.diag(V))


def spearman(a: list[float], b: list[float]) -> float:
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def compound(rets: list[float | None]) -> float | None:
    vals = [r for r in rets if r is not None]
    if not vals:
        return None
    g = 1.0
    for r in vals:
        g *= 1 + r
    return g - 1


def spread_stats(ls: dict[str, float], ff: dict[str, dict[str, float]]) -> dict:
    months = sorted(m for m in ls if m in ff)
    y = np.array([ls[m] for m in months])
    ones = np.ones((len(y), 1))
    _, t_mean = ols_nw(y, ones)
    fac = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
    X = np.column_stack([ones] + [np.array([ff[m][f] for m in months]) for f in fac])
    beta, t = ols_nw(y, X)
    return {"months": len(y), "first": months[0], "last": months[-1],
            "mean_monthly": float(y.mean()), "annualized": float((1 + y.mean()) ** 12 - 1), "t_mean": float(t_mean[0]),
            "alpha_monthly": float(beta[0]), "alpha_annualized": float((1 + beta[0]) ** 12 - 1), "t_alpha": float(t[0]),
            "loadings": {f: {"beta": float(b), "t": float(tt)} for f, b, tt in zip(fac, beta[1:], t[1:])}}


# ----------------------------------------------------------------------------- driver

def run(rows: list[dict], sic: dict[int, int], prices: Prices, ff: dict, last_formation: str) -> dict:
    uni = universe(rows, sic)
    add_relative(uni)
    tested = [r for r in uni if r["formed"] <= last_formation]
    for r in tested:
        s = prices.monthly(r["ticker"])
        r["_rets"] = month_returns(s, r["formed"]) if s else [None] * 12
        r["fwd_12m"] = compound(r["_rets"])

    res: dict = {"universe": {"rows": len(tested), "companies": len({r["cik"] for r in tested}),
                              "formations": sorted({r["formed"] for r in tested})}}
    for key in ("abs_verdict", "rel_verdict"):
        res[key] = {}
        for wt in ("ew", "vw"):
            b = bucket_series(tested, prices, key, wt)
            ls = {m: b["Dig deeper"][m] - b["Pass"][m] for m in b["Dig deeper"] if m in b["Pass"]}
            res[key][wt] = {
                "buckets": {v: {"annualized": float((1 + np.mean(list(b[v].values()))) ** 12 - 1),
                                "months": len(b[v])} for v in VERDICTS if b[v]},
                "long_short": spread_stats(ls, ff),
                "_ls_series": ls,
            }
        # How many names per bucket per formation, and how often each bucket beats the median stock.
        counts, hit = defaultdict(list), defaultdict(list)
        for f in res["universe"]["formations"]:
            yr = [r for r in tested if r["formed"] == f and r["fwd_12m"] is not None]
            med = float(np.median([r["fwd_12m"] for r in yr])) if yr else 0.0
            for v in VERDICTS:
                grp = [r for r in yr if r[key] == v]
                counts[v].append(len(grp))
                hit[v] += [r["fwd_12m"] > med for r in grp]
        res[key]["avg_names"] = {v: float(np.mean(counts[v])) for v in VERDICTS}
        res[key]["beat_median"] = {v: float(np.mean(hit[v])) if hit[v] else None for v in VERDICTS}
        # Rank IC of the continuous score against the next 12 months, per formation.
        pct = "abs_pct" if key == "abs_verdict" else "rel_pct"
        ics = []
        for f in res["universe"]["formations"]:
            yr = [r for r in tested if r["formed"] == f and r["fwd_12m"] is not None]
            if len(yr) > 30:
                ics.append(spearman([r[pct] for r in yr], [r["fwd_12m"] for r in yr]))
        res[key]["ic"] = {"mean": float(np.mean(ics)), "t": float(np.mean(ics) / (np.std(ics, ddof=1) / math.sqrt(len(ics)))),
                          "positive_years": int(sum(x > 0 for x in ics)), "years": len(ics),
                          "by_year": [round(x, 3) for x in ics]}

    # Survivorship: did companies that later disappeared score differently, on the dimensions
    # that don't need a price? If they skew toward Pass, their absence biases this test
    # AGAINST finding that Pass underperforms.
    def ex_val(r):
        s = [r.get(f"s_{d}") for d in ("growth", "profitability", "cash_conversion", "balance_sheet", "dilution")]
        s = [x for x in s if x is not None and not (isinstance(x, float) and math.isnan(x))]
        return sum(s) / (2 * len(s)) if s else None

    surv = {}
    for label, grp in (("listed today", [r for r in rows if r.get("listed_today") and not is_financial(sic.get(int(r["cik"]), 0))]),
                       ("no longer listed (sample)", [r for r in rows if not r.get("listed_today")])):
        vals = [ex_val(r) for r in grp if r["formed"] <= last_formation]
        vals = [v for v in vals if v is not None]
        surv[label] = {"rows": len(vals), "pass_share": float(np.mean([v < 0.40 for v in vals])) if vals else None,
                       "dig_share": float(np.mean([v >= 0.65 for v in vals])) if vals else None}
    res["survivorship"] = surv
    res["_tested"] = tested
    res["_universe_all"] = uni
    return res


def write_peers(uni: list[dict], path: Path) -> str:
    latest = max(r["formed"] for r in uni)
    tables = peer_tables([r for r in uni if r["formed"] == latest])
    safe = {g: {k: [v if math.isfinite(v) else (1e18 if v > 0 else -1e18) for v in vals] for k, vals in t.items()}
            for g, t in tables.items()}
    path.write_text(json.dumps({"as_of": latest, "min_peers": MIN_PEERS, "groups": safe}))
    return latest
