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
