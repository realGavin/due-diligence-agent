from ddagent.evidence import build_facts, fmt
from ddagent.filing import extract_sections, html_to_text

from .conftest import COMPANYFACTS, TENK_HTML, fid


def _latest(facts, label):
    return [f for f in facts if f.label == label][-1]


def test_annual_values_only_and_newest_tag_wins():
    facts = build_facts(COMPANYFACTS)
    rev = [f for f in facts if f.label == "Revenue"]
    assert [f.value for f in rev] == [800e6, 900e6, 1000e6, 1200e6]  # quarter row ignored
    assert "RevenueFromContract" in rev[-1].source


def test_derived_ratios_are_computed_in_code():
    facts = build_facts(COMPANYFACTS)
    assert round(_latest(facts, "Gross margin").value, 2) == 55.0
    assert round(_latest(facts, "Operating margin").value, 2) == 15.0
    assert round(_latest(facts, "Revenue growth (YoY)").value, 2) == 20.0
    assert round(_latest(facts, "Free cash flow").value) == 150e6
    assert round(_latest(facts, "Net debt (LT debt - cash)").value) == 100e6
    cagr = _latest(facts, "Revenue CAGR (3-yr)").value
    assert abs(cagr - ((1200 / 800) ** (1 / 3) - 1) * 100) < 1e-9
    assert "derived" in _latest(facts, "FCF margin").source


def test_restated_value_keeps_latest_filing():
    cf = {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": [
        {"start": "2024-01-01", "end": "2024-12-31", "val": 10, "form": "10-K", "filed": "2025-02-01", "accn": "a"},
        {"start": "2024-01-01", "end": "2024-12-31", "val": 12, "form": "10-K", "filed": "2026-02-01", "accn": "b"},
    ]}}}}}
    assert [f.value for f in build_facts(cf) if f.label == "Net income"] == [12]


def test_sections_skip_table_of_contents():
    sections = extract_sections(html_to_text(TENK_HTML))
    assert set(sections) == {"Business", "Risk Factors", "MD&A"}
    assert "industrial sensors" in sections["Business"]
    assert "contract manufacturer" in sections["Risk Factors"]
    assert "Unresolved" not in sections["Risk Factors"]
    assert "increased 20%" in sections["MD&A"]
    assert "99999" not in html_to_text(TENK_HTML)  # hidden inline-XBRL header removed


def test_fmt():
    assert fmt(1.234e9, "USD") == "$1.2B"
    assert fmt(-5e6, "USD") == "-$5.0M"
    assert fmt(12.345, "pct") == "12.3%"


def test_pack_ids_unique(pack):
    ids = [f.id for f in pack.facts] + [e.id for e in pack.excerpts]
    assert len(ids) == len(set(ids))
    assert fid(pack, "Revenue").startswith("F")


def test_em_dash_item_headings():
    # Costco's 10-K writes "Item 1A—Risk Factors"; the first version missed it.
    html = TENK_HTML.replace("Item 1A. Risk Factors</h2>", "Item 1A—Risk Factors</h2>").replace(
        "Item 7. Management", "Item 7—Management")
    sections = extract_sections(html_to_text(html))
    assert "contract manufacturer" in sections["Risk Factors"]
    assert "increased 20%" in sections["MD&A"]


def test_stale_tag_is_skipped():
    cf = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [{"start": "2024-01-01", "end": "2024-12-31", "val": 100, "form": "10-K",
                                        "filed": "2025-02-01", "accn": "a"}]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
            {"start": "2019-01-01", "end": "2019-12-31", "val": 5, "form": "10-K", "filed": "2020-02-01", "accn": "b"}]}},
    }}}
    assert not [f for f in build_facts(cf) if f.label == "Capital expenditures"]
