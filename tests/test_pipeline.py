"""End-to-end run with a scripted model: checks the grounding gate across the whole team."""
from ddagent.agents import Team
from ddagent.render import render

from .conftest import ScriptedLLM, fid, sid


def _script(pack):
    rev, growth, gm = fid(pack, "Revenue"), fid(pack, "Revenue growth (YoY)"), fid(pack, "Gross margin")
    fcf, net_debt = fid(pack, "Free cash flow"), fid(pack, "Net debt (LT debt - cash)")
    cust, cm, loan = sid(pack, "three largest"), sid(pack, "contract manufacturer"), sid(pack, "term loan")
    # Order matters: the final-memo prompt also mentions "red team", so it is matched first.
    return {
        "Business analyst": {"claims": [
            {"text": "Sells industrial sensors in 14 countries via direct sales.", "citations": [sid(pack, "14 countries")]},
            {"text": "Top three customers are 41% of revenue.", "citations": [cust]},
            {"text": "Market share is 30% of the global sensor market.", "citations": [cust]},  # fabricated
        ]},
        "Financial analyst": {"claims": [
            {"text": "Revenue grew 20% to $1.2B with a 55% gross margin.", "citations": [growth, rev, gm]},
            {"text": "Free cash flow was $150M.", "citations": [fcf]},
            {"text": "Net income margin is 25%.", "citations": [fid(pack, "Net margin")]},  # wrong: it's 12.5%
        ]},
        "Risk analyst": {"claims": [
            {"text": "About 70% of units come from a single contract manufacturer.", "citations": [cm]},
            {"text": "Management expects a recession next year.", "citations": ["S999"]},  # unknown id
        ]},
        "portfolio manager. Write": {"thesis": {
            "text": "A 20%-growth, cash-generative sensor maker with concentration risk.", "citations": [growth, fcf]}},
        "final investment memo": {
            "thesis": {"text": "Growing 20% with $150M FCF, but 41% customer concentration caps conviction.",
                       "citations": [growth, fcf, cust]},
            "bull": [{"text": "Net debt is only $100M.", "citations": [net_debt]}],
            "bear": [{"text": "Single-source manufacturing for ~70% of units.", "citations": [cm]}],
            "questions": ["What are contract renewal dates for the top three customers?"],
            "verdict": "Dig deeper",
            "verdict_rationale": {"text": "Quality growth; concentration needs primary research.", "citations": [cust]},
        },
        "red team": {"objections": [
            {"text": "41% customer concentration makes the growth fragile.", "citations": [cust], "severity": "high"},
            {"text": "Covenants on the $400 million loan limit flexibility.", "citations": [loan], "severity": "medium"},
            {"text": "Margins will fall to 40% next year.", "citations": [gm], "severity": "high"},  # invented
        ]},
    }


def test_full_run_drops_every_fabrication(pack):
    llm = ScriptedLLM(_script(pack))
    team = Team(llm, pack)
    memo = team.run()

    assert len(llm.calls) == 6  # 3 analysts + draft + red team + final
    reasons = {d["claim"]: d["reason"] for d in team.report.dropped}
    assert "Market share is 30% of the global sensor market." in reasons
    assert "Net income margin is 25%." in reasons
    assert "unknown" in reasons["Management expects a recession next year."]
    assert "Margins will fall to 40% next year." in reasons
    assert len(team.report.dropped) == 4

    # Nothing dropped reaches downstream agents.
    red_team_prompt = next(u for s, u in llm.calls if "red team" in s)
    assert "global sensor market" not in red_team_prompt
    assert all("40%" not in o.text for o in memo.objections)

    assert memo.verdict == "Dig deeper"
    assert "41%" in memo.thesis.text


def test_rendered_memo(pack):
    team = Team(ScriptedLLM(_script(pack)), pack)
    memo = team.run()
    md = render(memo, pack, team.report, "scripted")
    assert md.startswith("# Example Corp (EXMP)")
    assert "| Revenue | $1.2B | 2024-12-31 |" in md
    assert "Grounding report" in md and "passed verification" in md
    assert "Not investment advice" in md
    assert "Evidence cited" in md


def test_bad_verdict_is_normalized(pack):
    script = _script(pack)
    script["final investment memo"]["verdict"] = "STRONG BUY"
    assert Team(ScriptedLLM(script), pack).run().verdict == "Dig deeper"
