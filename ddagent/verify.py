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
    tol: float = 0.0  # half a unit in the last digit the writer used ($4.4B -> $0.05B)


def numbers_in(text: str) -> list[Number]:
    out = []
    for m in NUM.finditer(text):
        raw = m.group(0).strip()
        digits = m.group("num")
        n = float(digits.replace(",", ""))
        suf = (m.group("suf") or "").lower()
        start = m.start("num")
        before = text[max(0, start - 3):start]
        # Skip things that aren't claims: fiscal-period labels (FY25, Q3), years,
        # citation ids ([F12], [S3]) and small list ordinals.
        if not suf and "." not in digits and "," not in digits:
            if 1900 <= n <= 2100 or n < 10:
                continue
        if not suf and (before.upper().endswith(("FY", "Q", "F", "S", "[")) or before.upper().endswith("FY ")):
            continue
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        if suf in ("%", "percent", "pp"):
            kind, scale = "pct", 1.0
        elif suf == "x":
            kind, scale = "x", 1.0
        else:
            kind, scale = "abs", SCALE.get(suf, 1.0)
        n *= scale
        # A leading minus counts only when it isn't a range dash ("444.5M-444.8M", "2023-2025").
        neg = m.group("neg")
        if neg and m.start() > 0 and text[m.start() - 1].isalnum():
            neg = None
        if neg:
            n = -n
        out.append(Number(raw, n, kind, 0.5 * 10 ** -decimals * scale))
    return out


def _close(a: float, b: float, rel: float, abs_: float) -> bool:
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def _matches_fact(num: Number, f: Fact) -> bool:
    units = {"pct": ("pct",), "x": ("x",), "abs": ("USD", "shares")}[num.kind]
    if f.unit not in units:
        return False
    # Match if the fact, rounded to the precision the writer used, equals the number.
    # Sign is ignored so "net cash of $2.1B" can cite a net-debt fact of -$2.1B.
    tol = max(num.tol * 1.0001, 1e-9)
    if num.kind == "abs":
        tol = max(tol, 0.006 * abs(f.value))  # integer-rounded big numbers ($391B)
    return any(abs(num.value - t) <= tol for t in (f.value, -f.value))


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
