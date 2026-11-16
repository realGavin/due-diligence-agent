"""The grounding gate. It runs in code, not in a prompt, so the model can't talk its way past it.

A claim survives only if:
  1. it cites at least one id, and every id it cites exists in the evidence pack, and
  2. every number in its text traces to one of the CITED items. For a fact, the
     number has to equal the fact's value (with unit scaling and rounding tolerance).
     For an excerpt, the number has to appear verbatim in the excerpt's text.

A claim that fails is dropped, and the reason is recorded in the grounding report.
"""
from __future__ import annotations

import math
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
    start: int = 0
    end: int = 0


def numbers_in(text: str, claims_only: bool = True) -> list[Number]:
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
        if claims_only and not suf and "." not in digits and "," not in digits:
            if 1900 <= n <= 2100 or n < 10:
                continue
        if claims_only and not suf and (before.upper().endswith(("FY", "Q", "F", "S", "[")) or before.upper().endswith("FY ")):
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
        out.append(Number(raw, n, kind, 0.5 * 10 ** -decimals * scale, m.start(), m.end()))
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
    """The number must appear in the passage as a number, not as a fragment of another one.

    Either the passage states the same quantity (same kind, equal at the precision the claim
    was written with: "$4.5B" matches "$4.5 billion" and "4,538 million"), or, for plain
    amounts, the same digits appear as a whole token (tables written "in millions").
    """
    for m in numbers_in(e.text, claims_only=False):
        if m.kind == num.kind and abs(abs(m.value) - abs(num.value)) <= max(num.tol * 1.0001, 1e-9):
            return True
    if num.kind != "abs":
        return False
    digits = re.search(r"\d[\d,]*(?:\.\d+)?", num.raw).group(0).replace(",", "")
    body = e.text.replace(",", "")
    return re.search(rf"(?<![\d.]){re.escape(digits)}(?![\d]|\.\d)", body) is not None


@dataclass
class Verdict:
    ok: bool
    reason: str = ""


# Words that say WHICH ratio a number is. "6.6% YoY" must match the YoY-growth fact, not
# a 6.6% CAGR that happens to be cited in the same claim.
YOY = ("Revenue growth (YoY)", "Diluted share count change (YoY)")
LABEL_WORDS: list[tuple[str, tuple[str, ...]]] = [
    (r"\byoy\b|year[- ]over[- ]year", YOY),  # which YoY is settled by the value itself
    (r"revenue growth|\bgrew\b|\bgrowth\b", ("Revenue growth (YoY)", "Revenue CAGR (3-yr)")),
    (r"cagr|compound annual", ("Revenue CAGR (3-yr)",)),
    (r"gross(?: margin)?(?! profit)", ("Gross margin",)),
    (r"operating(?: margin)?(?! income| cash| expense| loss)", ("Operating margin",)),
    (r"net(?: income)? margin", ("Net margin",)),
    (r"fcf margin|free[- ]cash[- ]flow margin", ("FCF margin",)),
    (r"\broe\b|return on equity", ("Return on equity",)),
    (r"fcf yield|free[- ]cash[- ]flow yield", ("FCF yield",)),
    (r"p/e\b|price[- /]to[- ]earnings|earnings multiple", ("P/E (market cap / net income)",)),
    (r"p/fcf|price[- /]to[- ]free[- ]cash", ("P/FCF",)),
    (r"ev ?/ ?revenue|ev/sales|enterprise value", ("EV / revenue",)),
    (r"r&d", ("R&D as % of revenue",)),
    (r"dilut|share count", ("Diluted share count change (YoY)",)),
]


def bound_label(text: str, num: Number) -> tuple[str, ...] | None:
    """The ratio a pct/x number is attached to, if the wording makes that unambiguous.

    A keyword counts only if nothing separates it from the number: no other digits, no
    comma/semicolon, no "and". "64.1% gross margin, 42.8% operating margin" binds each
    number to its own label; the nearest eligible keyword wins, and a word after the number
    ("8.2% YoY") is preferred over one before it on ties.
    """
    if num.kind not in ("pct", "x"):
        return None
    low = text.lower()
    best: tuple[float, tuple[str, ...]] | None = None
    for pat, label in LABEL_WORDS:
        for m in re.finditer(pat, low):
            if m.start() >= num.end:
                gap, dist = low[num.end:m.start()], m.start() - num.end
            elif m.end() <= num.start:
                gap, dist = low[m.end():num.start], (num.start - m.end()) + 0.5
            else:
                continue
            if re.search(r"\d|[,;]|\band\b|\bvs\b|\bwhile\b", gap) or dist > 40:
                continue
            if best is None or dist < best[0]:
                best = (dist, label)
    return best[1] if best else None


# --- Support check -----------------------------------------------------------------------
# The number checks above can't see a claim with no numbers in it: a qualitative claim cited
# to the wrong passage used to pass untouched. Two checks close most of that gap, in code:
#   1. a direct quote must appear in a cited passage, word for word;
#   2. a qualitative claim citing passages must share enough of its distinctive words with
#      them. Words are weighted by how rare they are in this company's evidence, so generic
#      words ("revenue", "customers") count for little and specific ones ("Broadcom") a lot.
# This checks that the claim and the passage are about the same thing. It does not check
# that the passage says what the claim says: a claim can reuse a passage's words and still
# get it wrong. eval/planted_errors.py measures both what it catches and what it wrongly rejects.

SUPPORT_MIN = 0.20  # weighted share of the claim's distinctive words found in the cited passages

_STOP = set("""a an the and or but of to in on for with by as at from that this these those is are was
were be been being it its their our we they he she his her them not no nor so than then there which who
whom whose what when where while also into over under about after before more most less such can could
may might will would should has have had do does did each other any all some only very just both either
per via within without across between against up down out off same own new one two three""".split())
_SUFFIXES = ("ations", "ation", "ments", "ment", "ingly", "edly", "ings", "ing", "ied", "ies",
             "ity", "ed", "es", "ly", "al", "s")
_QUOTE = re.compile(r"[\"“”]([^\"“”]{12,}?)[\"“”]")


def _stem(w: str) -> str:
    for s in _SUFFIXES:
        if w.endswith(s) and len(w) - len(s) >= 4:
            return w[: -len(s)]
    return w


def _terms(text: str) -> set[str]:
    text = text.lower().replace("’", "'").replace("‘", "'")
    return {_stem(w) for w in re.findall(r"[a-z][a-z'&-]+", text) if len(w) >= 4 and w not in _STOP}


def _norm(text: str) -> str:
    """Words and digits only, so a quote ending in "." still matches a passage with "," there,
    and "$9.6 million" matches the filing's "$ 9.6 million". Page-break residue from 10-K
    text ("17 Table of Contents") is removed so it can't split a quoted sentence."""
    text = re.sub(r"\b\d{1,3}\s+Table of Contents\b", " ", text, flags=re.I)
    text = text.lower().replace("’", "").replace("‘", "").replace("'", "")
    return " " + re.sub(r"[^a-z0-9]+", " ", text).strip() + " "


def support_score(text: str, cited: list, pack: EvidencePack) -> float:
    """Share of the claim's distinctive words (rarity-weighted) that appear in what it cites."""
    claim = _terms(text)
    if not claim:
        return 1.0
    docs = [_terms(e.text) for e in pack.excerpts]
    df: dict[str, int] = {}
    for d in docs:
        for w in d:
            df[w] = df.get(w, 0) + 1
    n = len(docs)

    def weight(w: str) -> float:
        return math.log((n + 1) / (df.get(w, 0) + 1)) + 1

    source: set[str] = set()
    for x in cited:
        source |= _terms(x.text if isinstance(x, Excerpt) else x.label)
    total = sum(weight(w) for w in claim)
    return sum(weight(w) for w in claim if w in source) / total


def check_support(text: str, cited: list, pack: EvidencePack, judgment: bool = False) -> Verdict:
    """judgment=True for the PM's thesis and verdict rationale: they summarize findings that
    already passed the gate, so they're held to the quote check but not the word-overlap check."""
    passages = [x for x in cited if isinstance(x, Excerpt)]
    if not passages:
        return Verdict(True)  # facts are checked by value, above
    body = " ".join(_norm(p.text) for p in passages)
    for m in _QUOTE.finditer(text):
        parts = [_norm(p) for p in re.split(r"\.\.\.|…|\[[^\]]*\]", m.group(1))]
        if any(p and p not in body for p in parts):
            return Verdict(False, f"quote “{m.group(1)[:60]}” is not in the cited passage(s)")
    if not judgment and not numbers_in(text):
        s = support_score(text, cited, pack)
        if s < SUPPORT_MIN:
            return Verdict(False, f"claim isn't supported by the cited passage(s) (word support {s:.0%})")
    return Verdict(True)


def check_claim(text: str, citations: list[str], pack: EvidencePack, support: bool = True,
                judgment: bool = False) -> Verdict:
    if not citations:
        return Verdict(False, "no citations")
    unknown = [c for c in citations if pack.get(c) is None]
    if unknown:
        return Verdict(False, f"cites unknown id(s) {unknown}")
    cited = [pack.get(c) for c in citations]
    if support:
        v = check_support(text, cited, pack, judgment)
        if not v.ok:
            return v
    for num in numbers_in(text):
        if any(isinstance(x, Excerpt) and _in_excerpt(num, x) for x in cited):
            continue
        facts = [x for x in cited if isinstance(x, Fact) and _matches_fact(num, x)]
        if not facts:
            return Verdict(False, f"number '{num.raw}' not supported by cited evidence {citations}")
        labels = bound_label(text, num)
        if labels and not any(f.label in labels for f in facts):
            return Verdict(False, f"number '{num.raw}' is described as {' / '.join(labels)} but matches "
                                  f"{', '.join(sorted({f.label for f in facts}))}")
    return Verdict(True)


@dataclass
class GroundingReport:
    proposed: int = 0
    kept: int = 0
    dropped: list[dict] = field(default_factory=list)
    by_stage: dict = field(default_factory=dict)  # stage -> [kept, proposed]

    def add(self, stage: str, text: str, v: Verdict) -> None:
        self.proposed += 1
        k = self.by_stage.setdefault(stage, [0, 0])
        k[1] += 1
        if v.ok:
            k[0] += 1
            self.kept += 1
        else:
            self.dropped.append({"stage": stage, "claim": text, "reason": v.reason})

    @property
    def rate(self) -> float:
        return self.kept / self.proposed if self.proposed else 1.0
