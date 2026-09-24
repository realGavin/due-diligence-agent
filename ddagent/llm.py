"""The model interface. It's one method wide, so the tests can swap in a scripted fake."""
from __future__ import annotations

import json
import os
import re
from typing import Protocol


class LLM(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class AnthropicLLM:
    def __init__(self, model: str | None = None, max_tokens: int = 4000):
        import anthropic  # imported lazily so the test suite doesn't need it

        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("DD_MODEL", "claude-sonnet-4-5")
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


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
