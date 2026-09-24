"""The grounding gate. It runs in code, not in a prompt, so the model can't talk its way past it.

A claim survives only if:
  1. it cites at least one id, and every id it cites exists in the evidence pack, and
  2. every number in its text traces to one of the CITED items. For a fact, the
     number has to equal the fact's value (with unit scaling and rounding tolerance).
     For an excerpt, the number has to appear verbatim in the excerpt's text.

A claim that fails is dropped, and the reason is recorded in the grounding report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .evidence import EvidencePack, Excerpt, Fact

NUM = re.compile(
    r"(?P<neg>[-−])?\$?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(?P<suf>%|percent|pp|x\b|trillion|billion|million|thousand|bn|[TBMK]\b)?",
    re.I,
)
SCALE = {"trillion": 1e12, "t": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "m": 1e6,
         "thousand": 1e3, "k": 1e3}


@dataclass
class Number:
    raw: str
    value: float
    kind: str  # "pct" | "x" | "abs"


def numbers_in(text: str) -> list[Number]:
    out = []
    for m in NUM.finditer(text):
        raw = m.group(0).strip()
        n = float(m.group("num").replace(",", ""))
        suf = (m.group("suf") or "").lower()
        # Skip years, citation ids ([F12], [S3]) and list ordinals: they aren't claims.
        if not suf and "." not in m.group("num") and "," not in m.group("num"):
            if 1900 <= n <= 2100 or n < 10:
                continue
        start = m.start()
        if start > 0 and text[start - 1] in "FS[" and not suf:
            continue
        if suf in ("%", "percent", "pp"):
            kind = "pct"
        elif suf == "x":
            kind = "x"
        else:
            kind = "abs"
            n *= SCALE.get(suf, 1.0)
        if m.group("neg"):
            n = -n
        out.append(Number(raw, n, kind))
    return out


def _close(a: float, b: float, rel: float, abs_: float) -> bool:
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def _matches_fact(num: Number, f: Fact) -> bool:
    targets = [f.value, abs(f.value)]
    if num.kind == "pct":
        return f.unit == "pct" and any(_close(num.value, t, 0.02, 0.15) for t in targets)
    if num.kind == "x":
        return f.unit == "x" and any(_close(num.value, t, 0.02, 0.02) for t in targets)
    # Absolute amounts: allow rounding to the precision the writer used ($394.3B, $394B).
    return f.unit in ("USD", "shares") and any(_close(num.value, t, 0.006, 0) for t in targets)


def _in_excerpt(num: Number, e: Excerpt) -> bool:
    digits = re.sub(r"[^\d.]", "", num.raw)
    body = e.text.replace(",", "")
    return bool(digits) and digits.replace(",", "") in body


@dataclass
class Verdict:
    ok: bool
    reason: str = ""


def check_claim(text: str, citations: list[str], pack: EvidencePack) -> Verdict:
    if not citations:
        return Verdict(False, "no citations")
    unknown = [c for c in citations if pack.get(c) is None]
    if unknown:
        return Verdict(False, f"cites unknown id(s) {unknown}")
    cited = [pack.get(c) for c in citations]
    for num in numbers_in(text):
        if not any(
            (isinstance(x, Fact) and _matches_fact(num, x)) or (isinstance(x, Excerpt) and _in_excerpt(num, x))
            for x in cited
        ):
            return Verdict(False, f"number '{num.raw}' not supported by cited evidence {citations}")
    return Verdict(True)


@dataclass
class GroundingReport:
    proposed: int = 0
    kept: int = 0
    dropped: list[dict] = field(default_factory=list)

    def add(self, stage: str, text: str, v: Verdict) -> None:
        self.proposed += 1
        if v.ok:
            self.kept += 1
        else:
            self.dropped.append({"stage": stage, "claim": text, "reason": v.reason})

    @property
    def rate(self) -> float:
        return self.kept / self.proposed if self.proposed else 1.0
