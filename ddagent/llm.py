"""The model interface: `complete` for reasoning over the evidence pack, and `research`
for live web search with citations. It's two methods wide so tests can swap in a fake."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Source:
    url: str
    title: str
    cited_text: str  # the exact passage the model is citing, returned by the API


@dataclass
class Segment:
    """One block of a research answer and the web passages it is cited to."""
    text: str
    sources: list[Source] = field(default_factory=list)


class LLM(Protocol):
    def complete(self, system: str, user: str) -> str: ...

    def research(self, system: str, question: str) -> list[Segment]: ...


class AnthropicLLM:
    def __init__(self, model: str | None = None, max_tokens: int = 4000):
        import anthropic  # imported lazily so the test suite doesn't need it

        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key.startswith("sk-ant-") or "your-key" in key:
            raise RuntimeError("Set ANTHROPIC_API_KEY to your real key (from console.anthropic.com).")
        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("DD_MODEL", "claude-sonnet-5")
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    def research(self, system: str, question: str, max_searches: int = 4) -> list[Segment]:
        """Answer with Anthropic's server-side web search. Citations come back from the API
        with the exact cited passage, so the grounding gate can check numbers against them."""
        tool = {"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}
        messages: list = [{"role": "user", "content": question}]
        segments: list[Segment] = []
        for _ in range(4):  # long searches can pause; continue the same turn
            msg = self.client.messages.create(model=self.model, max_tokens=self.max_tokens, system=system,
                                              messages=messages, tools=[tool])
            for b in msg.content:
                if getattr(b, "type", "") != "text":
                    continue
                srcs = [Source(c.url, c.title or "", c.cited_text) for c in (b.citations or [])
                        if getattr(c, "type", "") == "web_search_result_location"]
                segments.append(Segment(b.text, srcs))
            if msg.stop_reason != "pause_turn":
                break
            messages = [*messages, {"role": "assistant", "content": msg.content}]
        return segments


def parse_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply, tolerating ```json fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    if start < 0:
        raise ValueError("model reply contained no JSON object")
    depth = 0
    in_str = esc = False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start: i + 1])
    raise ValueError("unterminated JSON object in model reply")
