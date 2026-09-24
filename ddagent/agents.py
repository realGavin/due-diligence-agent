"""The team: three specialist analysts, a red team, and an orchestrator (PM).

Each agent gets a role and a slice of the evidence pack, and has to answer in JSON
with citations. Every claim then goes through verify.check_claim before anyone
downstream is allowed to see it. That means the red team attacks only grounded
claims, and the PM writes only from what survived.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .evidence import EvidencePack
from .llm import LLM, parse_json
from .verify import GroundingReport, check_claim

RULES = """Rules you must follow:
- Use ONLY the evidence pack below. No outside knowledge about this company, its stock price, valuation, or news.
- Every claim must cite one or more evidence ids, e.g. ["F3", "S12"]. Cite the id that actually contains the number or statement.
- Do not compute new numbers: no sums, differences or ranges you worked out yourself. Quote numbers exactly as they appear in the cited evidence (rounding like $391.0B -> $391B is fine). If two figures matter together, state both (\"26% and 16%\"), not their total.\n- Cite the specific fact id for every number you use, including prior-year values.
- Prefer specific, decision-relevant claims over generic ones. 4-7 claims.
Reply with JSON only."""

CLAIMS_SCHEMA = '{"claims": [{"text": "...", "citations": ["F1"]}]}'


@dataclass
class Claim:
    text: str
    citations: list[str]
    author: str
    severity: str | None = None  # red-team objections only

    def to_prompt(self, i: int) -> str:
        sev = f" (severity: {self.severity})" if self.severity else ""
        return f"C{i}. [{self.author}]{sev} {self.text} {json.dumps(self.citations)}"


@dataclass
class Memo:
    company: str
    ticker: str
    filing_url: str
    thesis: Claim
    bull: list[Claim]
    bear: list[Claim]
    questions: list[str]
    verdict: str  # the PM's own view; the published verdict comes from the scorecard
    verdict_rationale: Claim
    analyst_claims: list[Claim] = field(default_factory=list)
    objections: list[Claim] = field(default_factory=list)
    research: list = field(default_factory=list)  # ResearchAnswer
    valuation: list = field(default_factory=list)  # Fact ids added by research
    scorecard: object = None  # scorecard.Scorecard


ANALYSTS = {
    "Business analyst": (
        "You analyze the business model: what the company sells, to whom, how it makes money, "
        "segments, competitive position, and sources of durable advantage (or lack of it).",
        ("Business",),
    ),
    "Financial analyst": (
        "You analyze financial quality from the facts: growth, margins and their direction, cash conversion "
        "(FCF vs net income), capital intensity, balance-sheet leverage, and shareholder dilution.",
        (),  # facts only
    ),
    "Risk analyst": (
        "You identify the risks most likely to impair the investment case, from the risk factors and MD&A, "
        "separating company-specific risks from boilerplate every filer lists.",
        ("Risk Factors", "MD&A"),
    ),
}


class Team:
    def __init__(self, llm: LLM, pack: EvidencePack):
        self.llm = llm
        self.pack = pack
        self.report = GroundingReport()
        self.trace: list[dict] = []

    # -- plumbing --------------------------------------------------------------
    def _ask(self, stage: str, system: str, user: str) -> dict:
        raw = self.llm.complete(system, user)
        self.trace.append({"stage": stage, "reply": raw})
        return parse_json(raw)

    def _keep(self, stage: str, author: str, items: list[dict], with_severity: bool = False) -> list[Claim]:
        kept = []
        for it in items or []:
            text, cites = str(it.get("text", "")).strip(), [str(c) for c in it.get("citations", [])]
            v = check_claim(text, cites, self.pack)
            self.report.add(stage, text, v)
            if v.ok:
                kept.append(Claim(text, cites, author, it.get("severity") if with_severity else None))
        return kept

    # -- stages ----------------------------------------------------------------
    def analyst(self, role: str) -> list[Claim]:
        brief, sections = ANALYSTS[role]
        system = f"You are the {role} on an investment due-diligence team. {brief}\n\n{RULES}\nSchema: {CLAIMS_SCHEMA}"
        user = self.pack.to_prompt(sections)
        return self._keep(role, role, self._ask(role, system, user).get("claims", []))

    def draft_thesis(self, claims: list[Claim]) -> Claim | None:
        system = (
            "You are the portfolio manager. Write the single most defensible one-to-two sentence investment "
            f"thesis supported by the team's verified findings.\n\n{RULES}\n"
            'Schema: {"thesis": {"text": "...", "citations": ["F1"]}}'
        )
        user = self._findings(claims)
        kept = self._keep("PM draft", "PM", [self._ask("PM draft", system, user).get("thesis", {})])
        return kept[0] if kept else None

    def red_team(self, thesis: Claim, claims: list[Claim]) -> list[Claim]:
        system = (
            "You are the red team. Your job is to break the thesis: find the strongest evidence-backed reasons it "
            "could be wrong, where the analysts over-read the evidence, and what they ignored. Be specific and fair; "
            "an objection without evidence is worthless here.\n\n"
            f"{RULES}\n"
            'Schema: {"objections": [{"text": "...", "citations": ["S4"], "severity": "high|medium|low"}]}'
        )
        user = f"THESIS: {thesis.text} {json.dumps(thesis.citations)}\n\n{self._findings(claims)}"
        return self._keep("Red team", "Red team", self._ask("Red team", system, user).get("objections", []), True)

    def final_memo(self, thesis: Claim, claims: list[Claim], objections: list[Claim]) -> Memo:
        system = (
            "You are the portfolio manager writing the final investment memo after the red team review. "
            "Revise the thesis if the objections warrant it. The bull case keeps what survived; the bear case "
            "must honestly carry the strongest objections. List 4-6 diligence questions whose answers would most "
            "change the thesis (no citations needed; a research agent will try to answer them from public sources "
            "next, and anything it can't answer goes to a human). Give your own view: 'Dig deeper', 'Watch', or 'Pass'. "
            "This is research triage, not a buy/sell recommendation.\n\n"
            f"{RULES}\n"
            'Schema: {"thesis": {"text": "", "citations": []}, "bull": [{"text": "", "citations": []}], '
            '"bear": [{"text": "", "citations": []}], "questions": ["..."], '
            '"verdict": "Dig deeper|Watch|Pass", "verdict_rationale": {"text": "", "citations": []}}'
        )
        obj = "\n".join(o.to_prompt(i + 1) for i, o in enumerate(objections)) or "(none survived verification)"
        user = f"DRAFT THESIS: {thesis.text} {json.dumps(thesis.citations)}\n\n{self._findings(claims)}\n\nRED TEAM OBJECTIONS:\n{obj}"
        out = self._ask("PM final", system, user)

        final_thesis = (self._keep("PM final", "PM", [out.get("thesis", {})]) or [thesis])[0]
        rationale = (self._keep("PM final", "PM", [out.get("verdict_rationale", {})]) or [final_thesis])[0]
        verdict = out.get("verdict", "Dig deeper")
        if verdict not in ("Dig deeper", "Watch", "Pass"):
            verdict = "Dig deeper"
        return Memo(
            company=self.pack.company,
            ticker=self.pack.ticker,
            filing_url=self.pack.filing_url,
            thesis=final_thesis,
            bull=self._keep("PM final", "PM", out.get("bull", [])),
            bear=self._keep("PM final", "PM", out.get("bear", [])),
            questions=[str(q) for q in out.get("questions", [])][:6],
            verdict=verdict,
            verdict_rationale=rationale,
            analyst_claims=claims,
            objections=objections,
        )

    def _findings(self, claims: list[Claim]) -> str:
        body = "\n".join(c.to_prompt(i + 1) for i, c in enumerate(claims))
        return f"VERIFIED TEAM FINDINGS:\n{body}\n\n{self.pack.to_prompt()}"

    # -- the whole run ---------------------------------------------------------
    def run(self, research: bool = True) -> Memo:
        from .research import Researcher  # local import: research builds on Claim
        from .scorecard import score

        researcher = Researcher(self.llm, self.pack, self.report, self.trace) if research else None
        valuation = researcher.market_cap() if researcher else []  # multiples join the evidence pack

        with ThreadPoolExecutor(max_workers=len(ANALYSTS)) as ex:
            results = list(ex.map(self.analyst, ANALYSTS))
        claims = [c for r in results for c in r]
        if not claims:
            raise RuntimeError("No analyst claim survived verification; see the grounding report.")
        thesis = self.draft_thesis(claims) or claims[0]
        objections = self.red_team(thesis, claims)
        memo = self.final_memo(thesis, claims, objections)

        if researcher:
            with ThreadPoolExecutor(max_workers=4) as ex:
                memo.research = list(ex.map(researcher.answer, memo.questions))
        memo.valuation = [f.id for f in valuation]
        memo.scorecard = score(self.pack, objections)
        return memo
