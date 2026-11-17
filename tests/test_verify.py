from ddagent.verify import check_claim, numbers_in

from .conftest import fid, sid


def test_number_parsing():
    vals = [(n.raw, n.value, n.kind) for n in numbers_in("Revenue was $1.2B, up 20% vs 2023; FCF $150 million, 2.5x")]
    assert ("$1.2B", 1.2e9, "abs") in vals
    assert any(v == 20 and k == "pct" for _, v, k in vals)
    assert any(v == 150e6 for _, v, _ in vals)
    assert any(v == 2.5 and k == "x" for _, v, k in vals)
    assert not any(v == 2023 for _, v, _ in vals)  # years aren't claims


def test_supported_fact_numbers_pass(pack):
    v = check_claim("Revenue grew 20% to $1.2B.", [fid(pack, "Revenue growth (YoY)"), fid(pack, "Revenue")], pack)
    assert v.ok, v.reason


def test_rounding_tolerance(pack):
    assert check_claim("Gross margin reached 55%.", [fid(pack, "Gross margin")], pack).ok
    assert check_claim("Revenue of $1,200 million.", [fid(pack, "Revenue")], pack).ok


def test_fabricated_number_fails(pack):
    v = check_claim("Revenue grew 35% last year.", [fid(pack, "Revenue growth (YoY)")], pack)
    assert not v.ok and "35%" in v.reason


def test_number_must_come_from_the_cited_item(pack):
    # 20% growth is true, but the claim cites the gross-margin fact instead.
    assert not check_claim("Revenue grew 20%.", [fid(pack, "Gross margin")], pack).ok


def test_excerpt_numbers_must_be_verbatim(pack):
    s = sid(pack, "three largest customers")
    assert check_claim("Top three customers were 41% of revenue.", [s], pack).ok
    assert not check_claim("Top three customers were 45% of revenue.", [s], pack).ok


def test_uncited_and_unknown_ids_fail(pack):
    assert check_claim("A qualitative claim.", [], pack).reason == "no citations"
    assert "unknown" in check_claim("Something.", ["F999"], pack).reason


def test_qualitative_claims_pass_with_valid_citation(pack):
    assert check_claim("The company relies on one contract manufacturer.", [sid(pack, "contract manufacturer")], pack).ok


# --- Regressions from the first real run (NVDA, COST, ANET) ------------------------

def test_fiscal_period_labels_are_not_claims():
    assert [n.raw for n in numbers_in("Operating income rose from FY22 to FY25 and Q3 was strong")] == []


def test_range_dash_is_not_a_minus_sign():
    vals = [n.value for n in numbers_in("shares were flat at 444.5M-444.8M")]
    assert vals == [444.5e6, 444.8e6]


def test_rounding_uses_the_writers_precision(pack):
    # Net debt is $100M; "$0.1B" is a correct one-decimal rounding of it.
    assert check_claim("Net debt is only $0.1B.", [fid(pack, "Net debt (LT debt - cash)")], pack).ok
    # ...but "$0.2B" is not.
    assert not check_claim("Net debt is $0.2B.", [fid(pack, "Net debt (LT debt - cash)")], pack).ok


def test_derived_totals_are_rejected(pack):
    s = sid(pack, "three largest customers")
    assert not check_claim("Customers were 20% and 21% (41% combined).", [s], pack).ok


# --- Regressions found by the planted-error eval ------------------------------------

def test_excerpt_numbers_must_be_whole_tokens(pack):
    # "14" must not pass because "2014" or "914" appears somewhere in the passage.
    s = sid(pack, "14 countries")
    assert check_claim("Sells in 14 countries.", [s], pack).ok
    assert not check_claim("Sells in 12 countries.", [s], pack).ok
    assert not check_claim("Sells in 4 regions and 1,400 cities.", [s], pack).ok


def test_ratio_must_match_the_ratio_it_is_described_as(pack):
    g, gm, om = fid(pack, "Revenue growth (YoY)"), fid(pack, "Gross margin"), fid(pack, "Operating margin")
    # 15% is the operating margin; calling it growth is wrong even though a 15% fact is cited.
    assert not check_claim("Revenue grew 15% YoY.", [g, om], pack).ok
    assert check_claim("Revenue grew 20% YoY with a 55% gross margin and 15% operating margin.", [g, gm, om], pack).ok
    assert check_claim("Gross margin of 55%, operating margin 15%.", [gm, om], pack).ok
    assert not check_claim("Gross margin of 15%, operating margin 55%.", [gm, om], pack).ok


# --- Support check: claims with no numbers in them ----------------------------------

def test_qualitative_claim_cited_to_the_wrong_passage_fails(pack):
    # True of the contract-manufacturer passage, but cited to the competition passage.
    v = check_claim("The company depends on a single contract manufacturer for its finished units.",
                    [sid(pack, "measurement accuracy")], pack)
    assert not v.ok and "supported" in v.reason


def test_quote_must_appear_in_the_cited_passage(pack):
    s = sid(pack, "measurement accuracy")
    assert check_claim('Management says it competes "primarily on measurement accuracy and integration support."',
                       [s], pack).ok
    v = check_claim('Management says it competes "primarily on price and speed of delivery."', [s], pack)
    assert not v.ok and "quote" in v.reason


def test_quote_matching_ignores_punctuation_and_page_breaks():
    from ddagent.evidence import EvidencePack, Excerpt
    p = EvidencePack("X", "X", "u", [], [Excerpt("W1", "Web", "the mix of sales to large customers who 17 Table of "
                                                       "Contents generally receive lower pricing, and $ 9.6 million of "
                                                       "assets “we’re keeping”", "u", "t")])
    assert check_claim('"the mix of sales to large customers who generally receive lower pricing."', ["W1"], p).ok
    assert check_claim('"$9.6 million of assets"', ["W1"], p).ok
    assert check_claim("\"'we're keeping'\"", ["W1"], p).ok


def test_judgment_claims_skip_the_overlap_check_but_not_the_quote_check(pack):
    s = sid(pack, "three largest customers")
    assert check_claim("Quality growth; concentration needs primary research.", [s], pack, judgment=True).ok
    assert not check_claim('Management calls it "a fortress business."', [s], pack, judgment=True).ok


def test_support_check_can_be_turned_off(pack):
    s = sid(pack, "measurement accuracy")
    assert check_claim("The company depends on a single contract manufacturer.", [s], pack, support=False).ok


# --- Meaning check (ddagent.judge) -------------------------------------------------

class FakeJudge:
    """Says 'supported' unless the claim contains a word from `reject`. Records calls."""
    def __init__(self, reject=()):
        self.reject, self.calls = reject, []

    def __call__(self, claim, passages, facts=None):
        self.calls.append(claim)
        bad = any(w in claim for w in self.reject)
        return (not bad), ("reverses the passage" if bad else "ok")


def test_judge_accepts_a_paraphrase_word_overlap_would_reject(pack):
    s = sid(pack, "contract manufacturer")
    claim = "Nearly all output comes from one outside factory partner, so a hiccup there could hold up deliveries."
    assert not check_claim(claim, [s], pack).ok          # word overlap: too few shared words
    assert check_claim(claim, [s], pack, judge=FakeJudge()).ok


def test_judge_rejects_reversed_meaning_and_says_why(pack):
    s = sid(pack, "contract manufacturer")
    v = check_claim("The company does not depend on a single contract manufacturer.", [s], pack,
                    judge=FakeJudge(reject=("does not",)))
    assert not v.ok and "don't support" in v.reason and "reverses" in v.reason


def test_judge_runs_only_after_code_checks_pass(pack):
    j = FakeJudge()
    s = sid(pack, "three largest customers")
    assert not check_claim("Customers were 55% of revenue.", [s], pack, judge=j).ok  # wrong number
    assert not check_claim('They call it "a fortress business model".', [s], pack, judge=j).ok       # fake quote
    assert j.calls == []


def test_judge_skips_judgment_claims_and_fact_only_claims(pack):
    j = FakeJudge(reject=("Quality",))
    assert check_claim("Quality growth; concentration needs research.", [sid(pack, "three largest customers")],
                       pack, judgment=True, judge=j).ok
    assert check_claim("Net debt is only $0.1B.", [fid(pack, "Net debt (LT debt - cash)")], pack, judge=j).ok
    assert j.calls == []


def test_support_judge_caches_and_rejects_unreadable_replies(tmp_path):
    from ddagent.judge import SupportJudge

    class Stub:
        model, n = "stub", 0
        def complete(self, system, user):
            self.n += 1
            return "not json" if "garbled" in user else '{"supported": true, "reason": "says so"}'

    llm = Stub()
    j = SupportJudge(llm, tmp_path / "cache.json")
    assert j("A claim.", ["A passage."]) == (True, "says so")
    assert j("A claim.", ["A passage."]) == (True, "says so") and llm.n == 1
    ok, reason = j("garbled claim", ["p"])
    assert not ok and "unreadable" in reason
    j.save()
    assert SupportJudge(Stub(), tmp_path / "cache.json")("A claim.", ["A passage."]) == (True, "says so")


def test_judge_is_shown_the_cited_figures(pack):
    seen = []

    def judge(claim, passages, facts=None):
        seen.append(facts)
        return True, "ok"

    s, f = sid(pack, "contract manufacturer"), fid(pack, "Net debt (LT debt - cash)")
    assert check_claim("Net debt is only $0.1B and the company relies on one contract manufacturer.", [f, s], pack,
                       judge=judge).ok
    assert seen and any("Net debt" in x for x in seen[0])


def test_judge_reads_the_verdict_from_a_reply_with_a_broken_reason():
    from ddagent.judge import _read
    assert _read('{"supported": true, "reason": "It says "same fact" here"}')["supported"] is True
    assert _read('```json\n{"supported": false, "reason": "no"}\n```')["supported"] is False
