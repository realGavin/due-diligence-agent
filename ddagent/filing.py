"""Turn a 10-K's HTML into a handful of verbatim, citable excerpts."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .evidence import Excerpt

# (section name, start pattern, end pattern). Each heading shows up at least twice,
# once in the table of contents and once in the body, so for every start match we
# cut to the next end match and keep the LONGEST span, which is the real body.
SECTIONS = [
    ("Business", r"item\s*1\.?\s*business", r"item\s*1a\.?\s*risk\s*factors"),
    ("Risk Factors", r"item\s*1a\.?\s*risk\s*factors", r"item\s*1b\.?|item\s*1c\.?|item\s*2\.?\s*properties"),
    ("MD&A", r"item\s*7\.?\s*management[’'`s]*\s*discussion", r"item\s*7a\.?|item\s*8\.?\s*financial"),
]


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for hidden in soup.select('[style*="display:none"]'):  # inline XBRL header blocks
        hidden.decompose()
    text = soup.get_text("\n")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def extract_sections(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, start, end in SECTIONS:
        best = ""
        for m in re.finditer(start, text, flags=re.I):
            nxt = re.compile(end, flags=re.I).search(text, m.end())
            span = text[m.end(): nxt.start() if nxt else len(text)]
            if len(span) > len(best):
                best = span
        if best.strip():
            out[name] = best.strip()
    return out


def chunk(text: str, target: int = 900) -> list[str]:
    """Split into roughly paragraph-sized pieces without cutting sentences."""
    # Lines shorter than 40 chars are page numbers, headers and table debris.
    paras = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]
    chunks, cur = [], ""
    for p in paras:
        p = " ".join(p.split())
        if len(cur) + len(p) > target and cur:
            chunks.append(cur)
            cur = ""
        cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur)
    return chunks


# Budget per section, so one call's evidence pack stays around 15-20k tokens.
BUDGET = {"Business": 14, "Risk Factors": 18, "MD&A": 16}


def build_excerpts(html: str) -> list[Excerpt]:
    sections = extract_sections(html_to_text(html))
    excerpts: list[Excerpt] = []
    for name, _, _ in SECTIONS:
        for piece in chunk(sections.get(name, ""))[: BUDGET[name]]:
            excerpts.append(Excerpt(f"S{len(excerpts) + 1}", name, piece))
    return excerpts
