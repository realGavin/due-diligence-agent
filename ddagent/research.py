"""The research agent: live web search, held to the same grounding gate as everything else.

The API returns every citation with the exact passage it points to (cited_text). Each
passage becomes a W-id excerpt in the evidence pack, so a research claim goes through
check_claim like any other: numbers in the claim have to appear in the passages it cites.
Anything the model writes without a citation that contains a number is dropped.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date

from .agents import Claim
from .evidence import EvidencePack, Excerpt, Fact
from .llm import LLM, Segment
from .verify import GroundingReport, check_claim, numbers_in

SYSTEM = (
    "You are the research agent on an investment due-diligence team. Use web search to answer from "
    "reliable public sources: company investor relations, earnings releases and call transcripts, SEC "
    "filings, and reputable financial press. Prefer the most recent information and say when it is dated. "
    "Answer in 2-4 short sentences of findings, and quote figures exactly as the source states them. Do not "
    "speculate. If reliable public information does not exist, or answering requires access to management "
    "or private data, reply with exactly: UNANSWERED: <one-line reason>"
)


@dataclass
class ResearchAnswer:
    question: str
    claims: list[Claim] = field(default_factory=list)
    unanswered: str = ""  # reason, if the question stays with a human


class Researcher:
    def __init__(self, llm: LLM, pack: EvidencePack, report: GroundingReport, trace: list[dict]):
        self.llm, self.pack, self.report, self.trace = llm, pack, report, trace
        self._lock = threading.Lock()  # questions are researched in parallel; ids must stay unique

    def _ingest(self, stage: str, segments: list[Segment]) -> list[Claim]:
        """Register cited passages as W-evidence, then gate each cited segment as a claim."""
        with self._lock:
            return self._ingest_locked(stage, segments)

    def _ingest_locked(self, stage: str, segments: list[Segment]) -> list[Claim]:
        claims: list[Claim] = []
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            if not seg.sources:
                if numbers_in(text):  # an uncited number is exactly what we refuse to pass on
                    self.report.add(stage, text, check_claim(text, [], self.pack))
                continue
            ids = []
            for src in seg.sources:
                existing = next((e for e in self.pack.excerpts
                                 if e.section == "Web" and e.text == src.cited_text and e.url == src.url), None)
                if existing is None:
                    existing = Excerpt(self.pack.next_id("W"), "Web", src.cited_text, src.url, src.title)
                    self.pack.excerpts.append(existing)
                if existing.id not in ids:
                    ids.append(existing.id)
            v = check_claim(text, ids, self.pack)
            self.report.add(stage, text, v)
            if v.ok:
                claims.append(Claim(text, ids, "Research"))
        return claims

    def _run(self, stage: str, question: str) -> list[Segment]:
        try:
            segs = self.llm.research(SYSTEM, question)
        except Exception as exc:  # e.g. web search not enabled for this API org; degrade, don't crash
            segs = [Segment(f"UNANSWERED: web search failed ({type(exc).__name__}: {str(exc)[:120]})")]
        self.trace.append({"stage": stage, "question": question,
                           "reply": [{"text": s.text, "sources": [vars(x) for x in s.sources]} for s in segs]})
        return segs

    def answer(self, question: str) -> ResearchAnswer:
        q = f"Company: {self.pack.company} ({self.pack.ticker}).\nQuestion: {question}"
        segs = self._run("Research", q)
        joined = " ".join(s.text for s in segs).strip()
        if "UNANSWERED:" in joined:
            return ResearchAnswer(question, unanswered=joined.split("UNANSWERED:", 1)[1].strip()[:200])
        claims = self._ingest("Research", segs)
        if not claims:
            return ResearchAnswer(question, unanswered="no answer survived source verification")
        return ResearchAnswer(question, claims)

    def market_cap(self) -> list[Fact]:
        """Find a cited market cap, then compute multiples in code. Returns the new facts."""
        q = (f"What is the current market capitalization of {self.pack.company} (ticker {self.pack.ticker}) "
             "in US dollars? State the figure and the date it applies to.")
        claims = self._ingest("Valuation", self._run("Valuation", q))
        for c in claims:
            caps = [n for n in numbers_in(c.text) if n.kind == "abs" and n.value >= 1e8]
            if caps:
                return self.pack.add_valuation(caps[0].value, date.today().isoformat(),
                                               f"web: {', '.join(c.citations)} (research agent)")
        return []
