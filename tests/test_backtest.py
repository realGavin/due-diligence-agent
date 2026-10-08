"""Point-in-time data, sector-relative scoring, portfolio math, regressions and the verdict ledger.
All offline: synthetic filings and prices."""
import io
import math
import zipfile

import numpy as np
import pytest

from backtest import analyze, data, panel
from ddagent import ledger
from ddagent.evidence import EvidencePack, build_facts
from ddagent.pit import as_of, latest_10k_filed, shares_outstanding
from ddagent.prices import Series, parse_chart
from ddagent.scorecard import metrics, percentile, pick_group, score_relative

from .conftest import COMPANYFACTS


# ----------------------------------------------------------------------------- point in time

def test_as_of_hides_filings_not_yet_public():
    view = as_of(COMPANYFACTS, "2024-06-30")  # FY2024 10-K is filed 2025-02-10
    facts = {f.label: f for f in build_facts(view)}
    assert facts["Revenue"].period == "2023-12-31" and facts["Revenue"].value == 1000e6
    assert latest_10k_filed(COMPANYFACTS, "2024-06-30") == "2024-02-10"
    assert latest_10k_filed(COMPANYFACTS) == "2025-02-10"
    full = {f.label: f for f in build_facts(COMPANYFACTS)}
    assert full["Revenue"].value == 1200e6  # nothing is lost without a cutoff


def test_restatement_filed_later_is_invisible_earlier():
    cf = {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [
        {"start": "2023-01-01", "end": "2023-12-31", "val": 100, "form": "10-K", "filed": "2024-02-01"},
        {"start": "2023-01-01", "end": "2023-12-31", "val": 60, "form": "10-K", "filed": "2025-02-01"},  # restated
    ]}}}}}
    early = as_of(cf, "2024-06-30")["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]
    assert [r["val"] for r in early] == [100]


def test_shares_outstanding_sums_share_classes_on_latest_cover():
    cf = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2024-01-20", "val": 90, "filed": "2024-02-01", "accn": "a"},
        {"end": "2025-01-20", "val": 100, "filed": "2025-02-01", "accn": "b"},  # class A
        {"end": "2025-01-20", "val": 20, "filed": "2025-02-01", "accn": "b"},   # class B
    ]}}}}}
    assert shares_outstanding(cf) == (120.0, "2025-01-20")
    assert shares_outstanding(as_of(cf, "2024-12-31")) == (90.0, "2024-01-20")


# ----------------------------------------------------------------------------- prices

def _chart(closes, adj, splits=None):
    ts = [1672531200 + i * 31 * 86400 for i in range(len(closes))]  # monthly-ish from 2023-01-01
    ev = {str(t): {"date": t, "numerator": n, "denominator": d} for t, n, d in (splits or [])}
    return {"chart": {"result": [{"timestamp": ts, "events": {"splits": ev},
                                  "indicators": {"quote": [{"close": closes}], "adjclose": [{"adjclose": adj}]}}]}}


def test_raw_price_undoes_later_splits():
    ts_split = 1672531200 + 2 * 31 * 86400 + 86400  # a 4-for-1 split after the third bar
    s = parse_chart("X", _chart([25.0, 26.0, 27.0, 28.0], [24.0, 25.0, 26.0, 27.0], [(ts_split, 4, 1)]))
    assert s.months[0] == "2023-01-31"
    assert s.raw_price(0) == 100.0  # quoted $100 before the split
    assert s.raw_price(3) == 28.0


# ----------------------------------------------------------------------------- relative scoring

def test_percentile_and_relative_scores():
    peers = sorted([float(x) for x in range(1, 31)])  # 30 peers, values 1..30
    assert percentile(30.5, peers) == 1.0 and percentile(0, peers) == 0.0
    tables = {"growth": peers, "op_margin": peers, "roe": peers, "cash_conversion": peers,
              "leverage_years": peers, "dilution": peers, "fcf_yield": peers}
    top = {"growth": 29, "op_margin": 29, "cash_conversion": 29, "leverage_years": 1, "dilution": 1, "fcf_yield": 29}
    sc = score_relative(top, tables, "sic2:73")
    assert sc.verdict == "Dig deeper" and sc.points == sc.possible == 12
    assert "SIC 73 peers" in sc.lines[0].basis
    bottom = {k: (1 if k not in ("leverage_years", "dilution") else 29) for k in top}
    assert score_relative(bottom, tables, "All").verdict == "Pass"
    # Too few peers: the dimension is not scored rather than guessed.
    assert score_relative(top, {"growth": peers[:5]}, "All").possible == 0


def test_metrics_rank_automatic_fails_last(pack):
    pack.add_valuation(3.0e9, "2025-06-30", "test")
    m = metrics(pack)
    assert m["growth"] == pytest.approx(20.0) and m["fcf_yield"] == pytest.approx(5.0)
    assert 0 < m["leverage_years"] < 1
    bad = EvidencePack("B", "B", "")
    from ddagent.evidence import Fact
    bad.facts = [Fact("F1", "Free cash flow", -5, "USD", "2024-12-31", ""), Fact("F2", "Net income", 10, "USD", "2024-12-31", ""),
                 Fact("F3", "Net debt (LT debt - cash)", 50, "USD", "2024-12-31", ""),
                 Fact("F4", "Market cap", 100, "USD", "2025-06-30", "")]
    mb = metrics(bad)
    assert mb["cash_conversion"] == -math.inf and mb["leverage_years"] == math.inf and mb["fcf_yield"] == -math.inf


def test_peer_group_falls_back_when_industry_is_thin():
    tables = {"sic2:73": {"growth": [1.0] * 5}, "div:Services": {"growth": [1.0] * 40}, "All": {"growth": [1.0] * 900}}
    assert pick_group(7372, tables) == "div:Services"
    assert pick_group(0, tables) == "All"


# ----------------------------------------------------------------------------- portfolios and stats

def test_buy_and_hold_portfolio_drifts_weights():
    a = [0.10] + [0.0] * 11
    b = [0.0, 0.10] + [0.0] * 10
    out = analyze.portfolio([(1.0, a), (1.0, b)])
    assert out[0] == pytest.approx(0.05)
    assert out[1] == pytest.approx(0.10 * 1.0 / 2.1)  # b is now the smaller position
    assert analyze.portfolio([(1.0, [None] * 12)])[0] == 0.0  # no data: cash


def test_newey_west_ols_recovers_coefficients():
    rng = np.random.default_rng(0)
    x = rng.normal(size=600)
    y = 0.01 + 0.5 * x + rng.normal(scale=0.1, size=600)
    beta, t = analyze.ols_nw(y, np.column_stack([np.ones(600), x]))
    assert beta[1] == pytest.approx(0.5, abs=0.02) and t[1] > 50


class FakePrices:
    def __init__(self, series):
        self.series = series

    def monthly(self, ticker, start=None, refresh=False):
        return self.series.get(ticker)


def _months(y0, n):
    out, y, m = [], y0, 1
    for _ in range(n):
        nxt = (y + (m == 12), m % 12 + 1)
        from datetime import date
        out.append(date.fromordinal(date(*nxt, 1).toordinal() - 1).isoformat())
        y, m = nxt
    return out


def test_end_to_end_on_a_synthetic_market():
    """Good fundamentals earn 2%/month, bad ones lose 1%: the test must find the spread."""
    months = _months(2012, 60)
    rows, series = [], {}
    rng = np.random.default_rng(1)
    for i in range(90):
        good = i % 3 == 0
        bad = i % 3 == 2
        drift = 0.02 if good else -0.01 if bad else 0.005
        adj = list(np.cumprod(1 + drift + rng.normal(scale=0.01, size=len(months))))
        series[f"T{i}"] = Series(f"T{i}", months, adj, adj, [])
        for y in (2012, 2013, 2014):
            lvl = 29 if good else 1 if bad else 15
            rows.append({"cik": i, "ticker": f"T{i}", "formed": f"{y}-06-30", "listed_today": True,
                         "mcap": 1e9 * (1 + i), "revenue": 1e9, "abs_pct": 0.9 if good else 0.1 if bad else 0.5,
                         "abs_verdict": "Dig deeper" if good else "Pass" if bad else "Watch",
                         "m_growth": lvl, "m_op_margin": lvl, "m_cash_conversion": lvl,
                         "m_leverage_years": 30 - lvl, "m_dilution": 30 - lvl, "m_fcf_yield": lvl,
                         "s_growth": 2, "s_profitability": 2, "s_cash_conversion": 2, "s_balance_sheet": 2, "s_dilution": 2})
    ff = {m[:7]: {"Mkt-RF": 0.0, "SMB": 0.0, "HML": 0.0, "RMW": 0.0, "CMA": 0.0, "Mom": 0.0, "RF": 0.0}
          for m in months}
    for k in ff:  # non-degenerate factors
        ff[k] = {f: float(v) for f, v in zip(ff[k], rng.normal(scale=0.02, size=7))}
    res = analyze.run(rows, {i: 7372 for i in range(90)}, FakePrices(series), ff, "2014-06-30")
    for key in ("abs_verdict", "rel_verdict"):
        b = res[key]["ew"]["buckets"]
        assert b["Dig deeper"]["annualized"] > b["Watch"]["annualized"] > b["Pass"]["annualized"]
        assert res[key]["ew"]["long_short"]["t_mean"] > 10
        assert res[key]["beat_median"]["Dig deeper"] > 0.9
        assert res[key]["ic"]["mean"] > 0.8
    peers_path = __import__("pathlib").Path("/tmp/_peers_test.json")
    assert analyze.write_peers(res["_universe_all"], peers_path) == "2014-06-30"


def test_panel_row_scores_with_price_and_shares():
    cf = {**COMPANYFACTS, "facts": {**COMPANYFACTS["facts"], "dei": {"EntityCommonStockSharesOutstanding": {
        "units": {"shares": [{"end": "2025-01-31", "val": 100e6, "filed": "2025-02-10", "accn": "x"}]}}}}}
    months = _months(2025, 12)
    s = Series("EXMP", months, [30.0] * 12, [30.0] * 12, [])
    r = panel.row_for(cf, "2025-06-30", "EXMP", FakePrices({"EXMP": s}))
    assert r["mcap"] == 3.0e9 and r["abs_verdict"] in ("Dig deeper", "Watch", "Pass")
    assert r["m_fcf_yield"] == pytest.approx(5.0)
    assert panel.row_for(cf, "2021-06-30", "EXMP", None) is None  # no 10-K public yet


def test_french_factor_parser(tmp_path, monkeypatch):
    csv_text = ("This file was created by CMPT_ME_BEME_OP_INV_RETS\n\n,Mkt-RF,SMB,HML,RMW,CMA,RF\n"
                "201207,  0.79, -0.24,  0.29, 0.10, 0.20, 0.00\n201208,  2.55, 0.50, 1.00, -0.3, 0.1, 0.01\n\n"
                " Annual Factors: January-December \n,Mkt-RF,SMB,HML,RMW,CMA,RF\n2012,  16.3, 0.5, 9.8, 1, 1, 0.06\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("F-F.csv", csv_text)
    monkeypatch.setattr(data, "CACHE", tmp_path)
    (tmp_path / "ff5.zip").write_bytes(buf.getvalue())
    out = data._french("unused", "ff5.zip")
    assert list(out) == ["2012-07", "2012-08"]
    assert out["2012-08"]["Mkt-RF"] == pytest.approx(0.0255)


# ----------------------------------------------------------------------------- ledger

def test_ledger_grades_due_verdicts_and_tracks_disagreement(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record(ledger.Entry("AAA", "2025-01-15", "u", "Dig deeper", 0.8, "Watch"), path)
    ledger.record(ledger.Entry("BBB", "2025-01-15", "u", "Pass", 0.1, "Pass", "Pass", 0.2), path)
    ledger.record(ledger.Entry("CCC", "2026-09-24", "u", "Watch", 0.5, "Watch"), path)  # not due yet
    ledger.record(ledger.Entry("AAA", "2025-01-15", "u", "Dig deeper", 0.8, "Watch"), path)  # rerun replaces
    months = _months(2024, 30)

    def flat(r):
        return Series("x", months, [100 * (1 + r) ** (i / 12) for i in range(30)],
                      [100 * (1 + r) ** (i / 12) for i in range(30)], [])
    prices = FakePrices({"AAA": flat(0.30), "BBB": flat(-0.20), "SPY": flat(0.10)})
    entries = ledger.grade(ledger.load(path), prices, today="2026-09-28")
    by = {e.ticker: e for e in entries}
    assert len(entries) == 3 and entries[0].due == "2026-01-15"
    assert by["AAA"].graded["scorecard_right"] and not by["AAA"].graded["pm_right"]
    assert by["BBB"].graded["scorecard_right"] and by["BBB"].graded["relative_right"]
    assert not by["CCC"].graded
    text = ledger.summarize(entries)
    assert "2 graded, 1 pending" in text and "scorecard right 1, PM right 0" in text


def test_memo_shows_peer_scorecard_and_track_record(pack):
    from ddagent.agents import Team
    from ddagent.render import render

    from .conftest import ScriptedLLM
    from .test_pipeline import _script

    team = Team(ScriptedLLM(_script(pack)), pack)
    memo = team.run(research=False)
    peers = {k: [float(x) for x in range(1, 31)] for k in ("growth", "op_margin", "roe", "cash_conversion",
                                                             "leverage_years", "dilution", "fcf_yield")}
    rel = score_relative(metrics(pack), peers, "sic2:73")
    calib = {"formations": ["2012", "2025"], "company_years": 21000,
             "abs_verdict": {"annualized_ew": {"Dig deeper": 0.12, "Watch": 0.09, "Pass": 0.04},
                             "beat_median": {"Dig deeper": 0.55, "Watch": 0.5, "Pass": 0.41}},
             "rel_verdict": {"annualized_ew": {"Dig deeper": 0.13, "Watch": 0.09, "Pass": 0.03},
                             "beat_median": {"Dig deeper": 0.56, "Watch": 0.5, "Pass": 0.40}}}
    md = render(memo, pack, team.report, "scripted", rel, calib)
    assert "## Against industry peers" in md and "SIC 73 peers" in md
    assert "Against industry peers: " in md.splitlines()[2]
    assert "Track record (2012–2025 backtest, 21,000 company-years)" in md


def test_market_cap_restates_shares_for_a_split_after_the_cover_date():
    cf = {**COMPANYFACTS, "facts": {**COMPANYFACTS["facts"], "dei": {"EntityCommonStockSharesOutstanding": {
        "units": {"shares": [{"end": "2025-01-31", "val": 10e6, "filed": "2025-02-10", "accn": "x"}]}}}}}
    months = _months(2025, 12)
    # 10-for-1 split on June 10: $30 after, $300 before; cover count (10M) is pre-split.
    s = Series("EXMP", months, [30.0] * 12, [30.0] * 12, [("2025-06-10", 10.0)])
    r = panel.row_for(cf, "2025-06-30", "EXMP", FakePrices({"EXMP": s}))
    assert r["price"] == 30.0 and r["mcap"] == pytest.approx(3.0e9)
