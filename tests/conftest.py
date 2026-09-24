"""Synthetic fixtures shaped exactly like SEC's APIs. The company is fictional ("Example Corp")."""
from __future__ import annotations

import json
import os

import pytest

os.environ["DD_NO_FETCH"] = "1"  # never hit the network from tests

from ddagent.evidence import EvidencePack, build_facts
from ddagent.filing import build_excerpts


def _flow(tag_rows):
    return {"units": {"USD": tag_rows}}


def _fy(end, start, val, filed, accn="0000000000-00-000001", form="10-K"):
    return {"start": start, "end": end, "val": val, "accn": accn, "fy": int(end[:4]), "fp": "FY", "form": form,
            "filed": filed}


YEARS = [("2021-12-31", "2021-01-01", "2022-02-10"), ("2022-12-31", "2022-01-01", "2023-02-10"),
         ("2023-12-31", "2023-01-01", "2024-02-10"), ("2024-12-31", "2024-01-01", "2025-02-10")]


def _series(vals):
    rows = [_fy(e, s, v, f) for (e, s, f), v in zip(YEARS, vals)]
    # A 10-K also restates quarters; these must be ignored.
    rows.append(_fy("2024-12-31", "2024-10-01", vals[-1] / 4, "2025-02-10"))
    return rows


def _instant(vals):
    return {"units": {"USD": [{"end": e, "val": v, "accn": "0000000000-00-000001", "form": "10-K", "fp": "FY",
                               "filed": f} for (e, _, f), v in zip(YEARS, vals)]}}


COMPANYFACTS = {
    "cik": 1,
    "entityName": "Example Corp",
    "facts": {"us-gaap": {
        # Old tag stops in 2022; the newer tag must win because its data is more recent.
        "SalesRevenueNet": _flow(_series([800e6, 900e6, 0, 0])[:2]),
        "RevenueFromContractWithCustomerExcludingAssessedTax": _flow(_series([800e6, 900e6, 1000e6, 1200e6])),
        "GrossProfit": _flow(_series([400e6, 450e6, 520e6, 660e6])),
        "OperatingIncomeLoss": _flow(_series([80e6, 99e6, 130e6, 180e6])),
        "NetIncomeLoss": _flow(_series([60e6, 70e6, 100e6, 150e6])),
        "NetCashProvidedByUsedInOperatingActivities": _flow(_series([90e6, 110e6, 140e6, 200e6])),
        "PaymentsToAcquirePropertyPlantAndEquipment": _flow(_series([20e6, 25e6, 30e6, 50e6])),
        "CashAndCashEquivalentsAtCarryingValue": _instant([100e6, 120e6, 150e6, 300e6]),
        "LongTermDebt": _instant([500e6, 480e6, 450e6, 400e6]),
        "StockholdersEquity": _instant([600e6, 650e6, 700e6, 750e6]),
    }},
}

TOC = """<p>Item 1. Business ..... 3</p><p>Item 1A. Risk Factors ..... 9</p>
<p>Item 1B. Unresolved Staff Comments</p><p>Item 7. Management's Discussion and Analysis ..... 30</p>
<p>Item 7A. Quantitative</p><p>Item 8. Financial Statements</p>"""

BODY = """
<h2>Item 1. Business</h2>
<p>Example Corp designs industrial sensors sold to manufacturers in 14 countries through a direct sales force.</p>
<p>Our three largest customers accounted for 41% of net revenue in fiscal 2024, and we expect customer concentration to remain significant.</p>
<p>We compete primarily on measurement accuracy and integration support; several competitors have substantially greater resources than we do.</p>
<h2>Item 1A. Risk Factors</h2>
<p>We depend on a single contract manufacturer for approximately 70% of our finished units, and any disruption could delay shipments.</p>
<p>Our $400 million term loan contains covenants that restrict our ability to incur additional indebtedness.</p>
<h2>Item 1B. Unresolved Staff Comments</h2><p>None.</p>
<h2>Item 7. Management’s Discussion and Analysis of Financial Condition</h2>
<p>Net revenue increased 20% in 2024, driven primarily by volume growth in the automotive end market, partially offset by pricing pressure.</p>
<p>Gross margin expanded as a result of manufacturing scale and a favorable product mix toward higher-accuracy sensors.</p>
<h2>Item 7A. Quantitative and Qualitative Disclosures</h2><p>Interest rate risk.</p>
<h2>Item 8. Financial Statements</h2><p>...</p>
"""

TENK_HTML = f"<html><body><div style=\"display:none\">ix header 99999</div>{TOC}{BODY}</body></html>"


@pytest.fixture
def pack() -> EvidencePack:
    p = EvidencePack("Example Corp", "EXMP", "https://www.sec.gov/Archives/edgar/data/1/x/exmp-10k.htm")
    p.facts = build_facts(COMPANYFACTS)
    p.excerpts = build_excerpts(TENK_HTML)
    return p


def fid(pack: EvidencePack, label: str) -> str:
    """Latest fact id for a label."""
    return [f for f in pack.facts if f.label == label][-1].id


def sid(pack: EvidencePack, needle: str) -> str:
    return next(e.id for e in pack.excerpts if needle in e.text)


class ScriptedLLM:
    """Replies by stage, recognized from the system prompt. Records every call.

    `research` maps a substring of the question to a list of Segments; unmatched
    questions come back UNANSWERED, like a question with no public answer."""

    def __init__(self, replies: dict[str, dict], research: dict | None = None):
        self.replies = replies
        self.research_replies = research or {}
        self.calls: list[tuple[str, str]] = []
        self.research_calls: list[str] = []

    def research(self, system: str, question: str):
        from ddagent.llm import Segment

        self.research_calls.append(question)
        for key, segs in self.research_replies.items():
            if key in question:
                return segs
        return [Segment("UNANSWERED: requires management access")]

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        for key, reply in self.replies.items():
            if key in system:
                return "Here you go:\n```json\n" + json.dumps(reply) + "\n```"
        raise AssertionError(f"unscripted stage: {system[:80]}")
