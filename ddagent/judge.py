"""Meaning check: does the cited passage actually support the claim?

The word-overlap check in verify.py can't read meaning. It rejects a correct claim that
paraphrases its source ("sales dropped" vs "revenue fell"), and it accepts a claim that
reuses the source's words but reverses them ("risk is declining" against a passage that
says it's rising). A second model call closes both gaps: it reads the claim and the cited
passages and answers supported / not supported.

It runs only after the checks in code have passed (ids exist, numbers match, quotes are
verbatim), so the model is never asked anything code can answer, and it only decides
support. eval/support_judge.py measures it against the word-overlap check.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .llm import LLM, parse_json

SYSTEM = """You check whether a research analyst's claim is supported by the sources it cites.

The sources are passages (from a 10-K or a web page) and, sometimes, figures. The figures
have already been checked against the claim's numbers, so treat them as true.

Answer "supported": true when every factual statement in the claim is stated in the sources
or directly implied by them.
- Paraphrase, summary and a partial version of what the sources say are fine.
- The claim may add the analyst's own reading of the facts (that something is a risk, raises
  doubt, signals weakness, matters more than something else). That's fine as long as the
  facts it rests on are in the sources.
- Answer false if a factual statement isn't in the sources, contradicts them, reverses a
  direction (rising vs falling, more vs less, will vs won't), changes who did or said
  something, states as fact what the source presents as an allegation, proposal or
  possibility, or if the sources are about something else.
- Judge only against the sources, not against what you know about the company.

Reply with JSON only, no other text: {"supported": true or false, "reason": "<one sentence>"}"""


def _read(reply: str) -> dict:
    """The JSON answer; if it won't parse (an unescaped quote in the reason, say), the verdict
    is read from the "supported" field directly. No verdict at all raises."""
    try:
        return parse_json(reply)
    except ValueError:
        m = re.search(r'"supported"\s*:\s*(true|false)', reply)
        if not m:
            raise
        r = re.search(r'"reason"\s*:\s*"(.*?)"\s*}?\s*$', reply, re.S)
        return {"supported": m.group(1) == "true", "reason": r.group(1) if r else ""}


class SupportJudge:
    """Callable: (claim, passages) -> (supported, reason). Answers are cached on disk by
    model + claim + passages, so evals rerun for free and give the same answer."""

    def __init__(self, llm: LLM, cache_path: str | Path | None = None, model_name: str = ""):
        self.llm = llm
        self.model_name = model_name or getattr(llm, "model", "")
        self.cache_path = Path(cache_path) if cache_path else None
        self.cache: dict[str, dict] = {}
        if self.cache_path and self.cache_path.exists():
            self.cache = json.loads(self.cache_path.read_text())
        self.calls = 0

    def _key(self, claim: str, passages: list[str], facts: list[str]) -> str:
        blob = json.dumps([self.model_name, SYSTEM, claim, passages, facts])
        return hashlib.sha256(blob.encode()).hexdigest()[:24]

    def __call__(self, claim: str, passages: list[str], facts: list[str] | None = None) -> tuple[bool, str]:
        facts = facts or []
        key = self._key(claim, passages, facts)
        if key not in self.cache:
            user = "CLAIM:\n" + claim + "\n\n" + "\n\n".join(
                f"PASSAGE {i + 1}:\n{p}" for i, p in enumerate(passages))
            if facts:
                user += "\n\nFIGURES (already verified):\n" + "\n".join(facts)
            self.calls += 1
            reply = self.llm.complete(SYSTEM, user)  # API errors propagate: never cached as a verdict
            try:
                out = _read(reply)
                self.cache[key] = {"supported": bool(out["supported"]), "reason": str(out.get("reason", ""))}
            except Exception:  # an unreadable answer rejects the claim; it's logged with the reply, not hidden
                self.cache[key] = {"supported": False, "reason": f"judge reply unreadable: {reply[:120]!r}"}
        hit = self.cache[key]
        return hit["supported"], hit["reason"]

    def save(self) -> None:
        if self.cache_path:
            self.cache_path.write_text(json.dumps(self.cache, indent=1, sort_keys=True))
