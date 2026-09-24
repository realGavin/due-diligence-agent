"""Web research (valuation + question answering) and the code-computed scorecard."""
from ddagent.agents import Claim, Team
from ddagent.evidence import EvidencePack, build_facts
from ddagent.llm import Segment, Source
from ddagent.render import render
from ddagent.research import Researcher
from ddagent.scorecard import score
from ddagent.verify import GroundingReport

from .conftest import ScriptedLLM, fid
from .test_pipeline import _script

IR = "https://investors.example.com/q4"
CAP = [Segment("Example Corp's market capitalization was about $3.0 billion as of September 2026.",
               [Source("https://markets.example.com/exmp", "EXMP quote", "Market cap: $3.0 billion (Sep 23, 2026)")])]


def _researcher(pack, research):
    return Researcher(ScriptedLLM({}, research), pack, GroundingReport(), [])


def test_market_cap_becomes_cited_fact_and_multiples_are_computed(pack):
    new = _researcher(pack, {"market capitalization": CAP}).market_cap()
    by = {f.label: f for f in new}
    assert by["Market cap"].value == 3.0e9 and by["Market cap"].source.startswith("web: W1")
    assert round(by["P/E (market cap / net income)"].value, 6) == 20.0  # 3.0B / 150M
    assert round(by["P/FCF"].value, 6) == 20.0
    assert round(by["FCF yield"].value, 6) == 5.0
    assert round(by["EV / revenue"].value, 4) == round((3.0e9 + 100e6) / 1200e6, 4)
    assert pack.get("W1").url == "https://markets.example.com/exmp"


def test_market_cap_not_in_cited_text_is_rejected(pack):
    bad = [Segment("Market cap is $9.9 billion.", [Source("https://x.example", "x", "Market cap: $3.0 billion")])]
    assert _researcher(pack, {"market capitalization": bad}).market_cap() == []
    assert not any(f.label == "Market cap" for f in pack.facts)


def test_research_answer_is_gated_like_everything_else(pack):
    segs = [
        Segment("Based on my search:"),  # connective text, no numbers: ignored
        Segment("Management said the top customer contract renews in 2027 and covers 18% of revenue.",
                [Source(IR, "Q4 call", "our largest customer, about 18% of revenue, renews its contract in 2027")]),
        Segment("Churn among the top three customers was 30% last year.",
                [Source(IR, "Q4 call", "we retained all three of our largest customers")]),  # number not in source
        Segment("Analysts expect 25% growth next year."),  # uncited number
    ]
    r = _researcher(pack, {"renewal": segs})
    ans = r.answer("When do top customer contracts come up for renewal?")
    assert [c.text for c in ans.claims] == [segs[1].text]
    assert ans.claims[0].citations == ["W1"]
    reasons = [d["reason"] for d in r.report.dropped]
    assert any("30%" in x for x in reasons) and "no citations" in reasons


def test_unanswerable_question_stays_with_a_human(pack):
    ans = _researcher(pack, {}).answer("What does the CEO privately think of pricing?")
    assert not ans.claims and "management" in ans.unanswered


def test_scorecard_on_fixture(pack):
    _researcher(pack, {"market capitalization": CAP}).market_cap()
    sc = score(pack, [Claim("x", ["S1"], "Red team", "high"), Claim("y", ["S1"], "Red team", "low")])
    got = {ln.dimension: ln.score for ln in sc.lines}
    assert got == {"Growth": 2, "Profitability": 2, "Cash conversion": 2, "Balance sheet": 1,
                   "Dilution": None, "Valuation": 2}
    assert sc.possible == 10 and sc.penalty == 0.5 and sc.points == 8.5
    assert sc.verdict == "Dig deeper"


def test_scorecard_on_a_declining_company():
    def rows(vals):
        yrs = [("2023-12-31", "2023-01-01"), ("2024-12-31", "2024-01-01"), ("2025-12-31", "2025-01-01")]
        return {"units": {"USD": [{"start": s, "end": e, "val": v, "form": "10-K", "filed": e[:4] + "-12-31",
                                   "accn": "a"} for (e, s), v in zip(yrs, vals)]}}

    def inst(vals):
        yrs = ["2023-12-31", "2024-12-31", "2025-12-31"]
        return {"units": {"USD": [{"end": e, "val": v, "form": "10-K", "filed": e[:4] + "-12-31", "accn": "a"}
                                  for e, v in zip(yrs, vals)]}}

    cf = {"facts": {"us-gaap": {
        "Revenues": rows([400e6, 330e6, 275e6]),
        "OperatingIncomeLoss": rows([-150e6, -140e6, -120e6]),
        "NetIncomeLoss": rows([-300e6, -160e6, 220e6]),  # one-off gain makes net income positive
        "NetCashProvidedByUsedInOperatingActivities": rows([-100e6, -90e6, -140e6]),
        "PaymentsToAcquirePropertyPlantAndEquipment": rows([10e6, 8e6, 5e6]),
        "CashAndCashEquivalentsAtCarryingValue": inst([190e6, 130e6, 215e6]),
        "LongTermDebt": inst([1.1e9, 1.1e9, 0.4e9]),
        "StockholdersEquity": inst([-500e6, -650e6, -300e6]),
    }}}
    p = EvidencePack("Decline Co", "DCLN", "https://example.com")
    p.facts = build_facts(cf)
    sc = score(p, [])
    assert {ln.dimension: ln.score for ln in sc.lines}["Cash conversion"] == 0
    assert sc.verdict == "Pass"


def test_full_run_with_research(pack):
    research = {"market capitalization": CAP,
                "renew": [Segment("The largest contract renews in 2027, covering 18% of revenue.",
                                  [Source(IR, "Q4 call", "about 18% of revenue, renews its contract in 2027")])]}
    team = Team(ScriptedLLM(_script(pack), research), pack)
    memo = team.run()
    assert memo.scorecard.verdict == "Dig deeper"
    assert len(memo.research) == 1 and memo.research[0].claims  # the one scripted question was answered
    md = render(memo, pack, team.report, "scripted")
    assert "## Scorecard" in md and "| Valuation | 2/2 |" in md
    assert "answered 1 from cited public sources" in md
    assert "[EXMP quote](https://markets.example.com/exmp)" in md
    assert "| Market cap | $3.0B |" in md


def test_truncated_citation_is_expanded_from_the_page(pack, monkeypatch):
    from ddagent import passages

    page = ("Intro text. According to BofA's read of the company's 10-K, Microsoft made up 26% of Arista's 2025 "
            "revenue, while Meta accounted for 16%. More text follows here.")
    monkeypatch.setattr(passages, "_page_text", lambda url: page)
    cited = "According to BofA&#x27;s read of the company&#x27;s 10-K, Microsoft made up 26% of Arista&#x27;s 2025 revenue, wh..."
    segs = [Segment("Microsoft made up 26% of 2025 revenue, while Meta accounted for 16%.",
                    [Source("https://news.example.com/a", "News", cited)])]
    ans = _researcher(pack, {"customers": segs}).answer("Who are the largest customers?")
    assert ans.claims, "16% is on the page, so the claim should pass once the passage is expanded"
    assert "Meta accounted for 16%" in pack.get(ans.claims[0].citations[0]).text


def test_truncated_citation_stays_strict_when_page_unavailable(pack):
    cited = "Microsoft made up 26% of Arista&#x27;s 2025 revenue, wh..."
    segs = [Segment("Microsoft made up 26% of revenue and Meta 16%.", [Source("https://x.example", "x", cited)])]
    assert not _researcher(pack, {"customers": segs}).answer("Who are the largest customers?").claims


def test_invalid_json_is_retried_then_skipped(pack):
    class Flaky:
        def __init__(self):
            self.n = 0

        def complete(self, system, user):
            self.n += 1
            return '{"claims": [{"text": "cut off'  # truncated every time

        def research(self, system, question):
            return [Segment("UNANSWERED: offline")]

    team = Team(Flaky(), pack)
    assert team.analyst("Risk analyst") == []
    assert any(d["reason"].startswith("model reply was not valid JSON") for d in team.report.dropped)
