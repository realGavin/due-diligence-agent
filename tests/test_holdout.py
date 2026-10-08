"""Holdout pipeline, offline: sample selection, pre-filing valuation, the stub-model run, and the analysis."""
import json
from dataclasses import asdict

import numpy as np
import pytest

from ddagent.prices import Series
from holdout import analyze, run, sample

from .conftest import COMPANYFACTS
from .test_backtest import FakePrices, _months


def test_tenk_in_window_uses_filing_dates_not_period_ends():
    cf = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {"end": "2024-06-30", "val": 1, "form": "10-K", "filed": "2024-08-20", "accn": "old"},
        {"end": "2025-06-30", "val": 2, "form": "10-K", "filed": "2025-08-22", "accn": "new"},
        {"end": "2025-03-31", "val": 3, "form": "10-Q", "filed": "2025-08-05", "accn": "q"},
    ]}}}}}
    assert sample.tenk_in_window(cf, "2025-08-01", "2025-09-30") == ("2025-08-22", "new")
    assert sample.tenk_in_window(cf, "2025-10-01", "2025-12-31") is None


def test_valuation_uses_the_month_end_before_filing_and_restates_splits():
    view = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2025-07-15", "val": 10e6, "filed": "2025-08-20", "accn": "x"}]}}}}}
    months = _months(2025, 12)
    s = Series("X", months, [30.0] * 12, [30.0] * 12, [("2025-07-20", 2.0)])
    mc, price, month = sample.market_cap_before(view, s, "2025-08-20")
    assert month == "2025-07-31" and price == 30.0
    assert mc == pytest.approx(10e6 * 2 * 30.0)  # the 2-for-1 split on July 20 doubles the July-15 count


def test_dry_run_end_to_end_on_a_real_shaped_pack(pack, tmp_path, monkeypatch):
    monkeypatch.setattr(sample, "PACKS", tmp_path)
    monkeypatch.setattr(run, "RESULTS", tmp_path / "results")
    pack.add_valuation(3.0e9, "2025-07-31", "test")
    meta = {"ticker": "EXMP", "cik": 1, "filed": "2025-08-20", "sic": 3829, "mcap": 3.0e9}
    (tmp_path / "EXMP.json").write_text(json.dumps({"meta": meta, "pack": asdict(pack)}))
    rows = run.run(["EXMP"], run.StubLLM, workers=1, runs_path=tmp_path / "runs.jsonl")
    r = rows[0]
    assert r["scorecard"]["verdict"] in ("Dig deeper", "Watch", "Pass")
    assert r["single"]["verdict"] == "Watch" and r["single"]["conviction"] == 3 and r["single"]["score"] == 50
    assert r["team"]["score"] == 50 and r["team"]["forecast"]["operating_margin_pct"] == 10.0
    assert r["team"]["pm_verdict"] == "Watch" and r["team"]["grounding"][0] > 0
    assert r["calls"] == 7 and r["tokens"][0] > 1000  # 1 single + 3 analysts + draft + red team + final
    assert run.run(["EXMP"], run.StubLLM, workers=1, runs_path=tmp_path / "runs.jsonl") == []  # resumes


def test_window_return_and_drawdown():
    months = _months(2025, 14)
    path = [100, 100, 100, 100, 100, 100, 100, 80, 60, 90, 110, 120, 120, 120]
    s = Series("X", months, path, path, [])
    ret, mdd = analyze.window(s, "2025-01-15")  # first month-end on/after is Jan 31
    assert ret == pytest.approx(0.20) and mdd == pytest.approx(-0.40)
    assert analyze.window(s, "2025-06-15") is None  # twelve months not yet observable


def _rows(n=200, seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        q = rng.random()
        v = "Dig deeper" if q > 0.66 else "Watch" if q > 0.33 else "Pass"
        pm = ["Pass", "Watch", "Dig deeper"][rng.integers(0, 3)]
        rows.append({"ticker": f"T{i}", "filed": "2025-08-15", "scorecard": {"verdict": v, "pct": q},
                     "single": {"verdict": pm, "conviction": int(rng.integers(1, 6))},
                     "team": {"pm_verdict": pm, "scorecard_with_penalty": q, "high_objections": int(rng.integers(0, 4))},
                     "tokens": [1000, 100], "calls": 7,
                     "ret": 0.3 * q + rng.normal(0, 0.1), "mdd": -rng.random() * 0.5, "spy": 0.1})
    med = float(np.median([r["ret"] for r in rows]))
    for r in rows:
        r["excess"] = r["ret"] - r["spy"]
        r["beat_median"] = r["ret"] > med
    return rows


def test_analysis_finds_the_planted_signal_and_not_the_noise():
    res = analyze.analyze(_rows())
    assert res["signals"]["scorecard"]["ic"] > 0.5 and res["signals"]["scorecard"]["ci"][0] > 0.3
    assert abs(res["signals"]["team_pm"]["ic"]) < 0.2  # random PM: no signal
    assert res["incremental"]["team_pm"]["scorecard_t"] > 5 and abs(res["incremental"]["team_pm"]["model_t"]) < 2.5
    assert res["buckets"]["scorecard"]["Dig deeper"]["beat_median"] > res["buckets"]["scorecard"]["Pass"]["beat_median"]
    md = analyze.report(res)
    assert "add anything the scorecard" in md and "When the PM and the scorecard disagreed" in md
    assert "Twelve-month returns: 200 companies" in md


def test_attach_outcomes_drops_incomplete_windows():
    months = _months(2025, 20)
    up = Series("A", months, [100 * 1.01 ** i for i in range(20)], [100 * 1.01 ** i for i in range(20)], [])
    rows = [{"ticker": "A", "filed": "2025-08-15"}, {"ticker": "B", "filed": "2025-08-15"}]
    out = analyze.attach_outcomes(rows, FakePrices({"A": up, "SPY": up}))
    assert [r["ticker"] for r in out] == ["A"] and out[0]["excess"] == pytest.approx(0)


def test_six_month_window():
    months = _months(2025, 14)
    path = [100.0 + i for i in range(14)]
    s = Series("X", months, path, path, [])
    ret, _ = analyze.window(s, "2025-03-10", 6)  # Mar 31 -> Sep 30
    assert ret == pytest.approx(108 / 102 - 1)


# ----------------------------------------------------------------------------- fundamentals

from holdout import fundamentals, outcomes  # noqa: E402


def _q(end, start, val, filed, form="10-Q"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form, "accn": "a"}


def _cf_quarters(rev, oi):
    """Quarters ending Mar/Jun 2025 and Mar/Jun 2026, as 10-Qs report them (with prior-year comparatives)."""
    ends = [("2025-03-31", "2025-01-01"), ("2025-06-30", "2025-04-01"), ("2026-03-31", "2026-01-01"), ("2026-06-30", "2026-04-01")]
    rows_r = [_q(e, st, v, "2026-08-05") for (e, st), v in zip(ends, rev)]
    rows_o = [_q(e, st, v, "2026-08-05") for (e, st), v in zip(ends, oi)]
    rows_r.append({**_q("2025-12-31", "2025-01-01", 999, "2026-02-20", "10-K")})  # annual: ignored (not 3 months)
    return {"facts": {"us-gaap": {"Revenues": {"units": {"USD": rows_r}}, "OperatingIncomeLoss": {"units": {"USD": rows_o}}}}}


def test_measure_post_filing_quarters_against_a_year_earlier():
    cf = _cf_quarters([100, 100, 105, 105], [20, 20, 18, 18])
    o = outcomes.measure(cf, "2025-12-31", filed_growth=16.0)
    assert o["quarters"] == ["2026-03-31", "2026-06-30"]
    assert o["post_growth"] == pytest.approx(5.0)
    assert o["growth_change"] == pytest.approx(-11.0)  # 16% -> 5%
    assert o["margin_change"] == pytest.approx((36 / 210 - 40 / 200) * 100)  # 20% -> 17.1%
    assert o["deteriorated"] is True  # growth slowed 10 points
    assert outcomes.realized_direction(o) == {"revenue_growth": "decelerate", "operating_margin": "compress"}
    assert outcomes.measure(cf, "2026-03-31", 15.0) is None  # only one quarter reported after June FY end


def test_quarterly_prefers_latest_filing_and_ignores_annual_rows():
    cf = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        _q("2026-03-31", "2026-01-01", 100, "2026-05-01"), _q("2026-03-31", "2026-01-01", 98, "2026-08-01"),
        _q("2025-12-31", "2025-01-01", 400, "2026-02-01", "10-K")]}}}}}
    assert outcomes.quarterly(cf, ("Revenues",)) == {"2026-03-31": 98.0}


def _fund_rows(n, seed, signal_strength=1.0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        q = rng.random()
        pm = ["Pass", "Watch", "Dig deeper"][min(2, int(q * 3))] if signal_strength else ["Pass", "Watch", "Dig deeper"][rng.integers(0, 3)]
        m = 6 * (q - 0.5) * signal_strength + rng.normal(0, 1)
        g = rng.normal(0, 5)
        o = {"margin_change": m, "growth_change": g, "deteriorated": m <= -3 or g <= -10}
        met = {"growth": rng.normal(10, 5), "op_margin": rng.normal(15, 5)}
        sig = q if signal_strength else rng.random()
        rows.append({"ticker": f"T{i}", "scorecard": {"pct": rng.random(), "verdict": "Watch"},
                     "single": {"verdict": "Watch", "score": 50,
                                "forecast": {"operating_margin_pct": met["op_margin"], "revenue_growth_pct": met["growth"]}},
                     "team": {"pm_verdict": pm, "high_objections": int(rng.integers(0, 3)), "score": round(sig * 100),
                              "forecast": {"operating_margin_pct": met["op_margin"] + 6 * (sig - 0.5),
                                           "revenue_growth_pct": met["growth"] + rng.normal(0, 3)}},
                     "metrics": met, "fund": o, "realized": outcomes.realized_direction(o)})
    return rows


def test_fundamentals_detects_a_model_signal_the_scorecard_lacks():
    test, dev = _fund_rows(300, 1), _fund_rows(80, 2)
    res = fundamentals.analyze(test, dev)
    assert res["ic"]["margin_change"]["team_pm"]["ci"][0] > 0.3
    assert abs(res["ic"]["margin_change"]["scorecard"]["ic"]) < 0.15
    assert res["incremental"]["margin_change:team_score"]["t"] > 5
    assert res["auc"]["team_score"]["auc"] > 0.6
    f = res["forecasts"]["margin_change"]["results"]
    assert f["Agent team (PM)"]["ci"][0] > 0.3 and f["Agent team (PM)"]["vs_ci"][0] > 0  # beats mean reversion
    assert "Single prompt" not in f  # always forecasts no change: nothing to rank
    md = fundamentals.report(res)
    assert "Primary: what happened to the business" in md and "Beyond the scorecard" in md


def test_fundamentals_reports_no_signal_when_there_is_none():
    res = fundamentals.analyze(_fund_rows(300, 3, signal_strength=0), _fund_rows(80, 4, 0))
    assert res["ic"]["margin_change"]["team_score"]["ci"][0] < 0 < res["ic"]["margin_change"]["team_score"]["ci"][1]
    assert abs(res["incremental"]["margin_change:team_score"]["t"]) < 2.5
    f = res["forecasts"]["margin_change"]["results"]["Agent team (PM)"]
    assert f["vs_ci"][0] < 0 < f["vs_ci"][1] or f["vs_ci"][1] < 0


def test_split_is_deterministic_and_about_one_fifth_dev():
    ts = [f"T{i}" for i in range(2000)]
    first = [run.split_of(t) for t in ts]
    assert first == [run.split_of(t) for t in ts]
    assert 0.17 < first.count("dev") / len(ts) < 0.23
