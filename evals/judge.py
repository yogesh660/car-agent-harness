"""LLM-as-judge: is every claim in the answer supported by the tool results?

The number check in grounding.py is strict but narrow. The judge also catches wrong
verdicts ("fair" when the tool said "above_market"), wrong cars and invented features.
It costs one extra model call per case, so it's opt-in: python -m evals.run --judge

Plain JSON in the reply instead of provider-specific structured output, so the same judge
works with Ollama, OpenAI-compatible servers and Anthropic.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

JUDGE_PROMPT = """\
You check answers from a used-car marketplace assistant.

You get the user's question, the raw tool results the assistant saw, and its answer.
Decide whether every factual claim in the answer is supported by the tool results.
Claims include listing ids, prices, mileage, years, cities, verdicts (fair / above / below
market) and which listing is cheapest or best value.

Not claims: general car knowledge, polite filler, stating assumptions, saying that
something was not found when the tool results show nothing was found.

Reply with JSON only, no other text:
{"supported": true or false, "unsupported_claims": ["..."], "reason": "one sentence"}
"""

_MAX_TOOL_CHARS = 12_000


class Verdict(BaseModel):
    supported: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    reason: str = ""
    error: str | None = None  # set when the judge's own reply could not be read


def _parse(text: str) -> Verdict:
    # models like to wrap JSON in ```json fences or add a sentence around it
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"judge reply has no JSON: {text[:200]!r}")
    return Verdict.model_validate(json.loads(match.group(0)))


def judge_answer(llm: Any, question: str, tool_outputs: list[str], answer: str) -> Verdict:
    tools_text = "\n\n".join(tool_outputs) or "(no tools were called)"
    if len(tools_text) > _MAX_TOOL_CHARS:
        tools_text = tools_text[:_MAX_TOOL_CHARS] + "\n...(truncated)"
    user = f"Question:\n{question}\n\nTool results:\n{tools_text}\n\nAnswer:\n{answer}"
    reply = llm.invoke([SystemMessage(JUDGE_PROMPT), HumanMessage(user)])
    content = reply.content if isinstance(reply.content, str) else str(reply.content)
    try:
        return _parse(content)
    except (ValueError, ValidationError) as exc:
        # an unreadable verdict is a judge failure, not an agent failure; kept out of the score
        return Verdict(supported=False, error=str(exc))
