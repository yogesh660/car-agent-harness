"""Deterministic faithfulness check: are the numbers in an answer backed by tool results?

Cheap, no model needed, runs on every eval case. It catches the most damaging kind of
hallucination for a marketplace: a made-up price, mileage or listing id.

Rules:
- every number in the answer must match a number from the tool results or the question,
- or be the difference between two of those numbers ("€1,550 below the estimate"),
- numbers >= 1000 may be rounded by up to 2% ("about €18,000" for 17,950),
- small numbers (< 10) are skipped: counts and ordinals ("3 cars", "2nd") are too noisy.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from itertools import combinations

# 15,000 / 15.000 / 15 000 / 18.5k / 60k / 4.5 / 42
_NUM = re.compile(
    r"""
    (?<![\w.,])
    (?P<int>\d{1,3}(?:(?P<sep>[,.\u202f ])\d{3})(?:(?P=sep)\d{3})*|\d+)
    (?:[.,](?P<frac>\d{1,2})(?!\d))?
    \s?(?P<k>[kK]\b)?
    """,
    re.VERBOSE,
)

MIN_CHECKED = 10
ROUNDING_TOLERANCE = 0.02


def extract_numbers(text: str) -> list[float]:
    numbers = []
    for m in _NUM.finditer(text):
        whole = m.group("int")
        if m.group("sep"):
            whole = re.sub(r"[,.\u202f ]", "", whole)
        value = float(f"{whole}.{m.group('frac')}") if m.group("frac") else float(whole)
        if m.group("k"):
            value *= 1000
        numbers.append(value)
    return numbers


def _numbers_in_json(value: object) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int | float):
        return [float(value)]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers_in_json(v)]
    if isinstance(value, list):
        return [n for v in value for n in _numbers_in_json(v)]
    if isinstance(value, str):
        return extract_numbers(value)
    return []


def source_numbers(tool_outputs: list[str], question: str = "") -> set[float]:
    found: set[float] = set(extract_numbers(question))
    for raw in tool_outputs:
        try:
            found.update(_numbers_in_json(json.loads(raw)))
        except (json.JSONDecodeError, TypeError):
            found.update(extract_numbers(raw))
    return found


def _close(a: float, b: float) -> bool:
    if a >= 1000 or b >= 1000:
        return abs(a - b) <= ROUNDING_TOLERANCE * max(a, b)
    return a == b


@dataclass
class GroundingResult:
    checked: int
    ungrounded: list[float] = field(default_factory=list)

    @property
    def grounded(self) -> bool:
        return not self.ungrounded


def check_grounding(answer: str, tool_outputs: list[str], question: str = "") -> GroundingResult:
    sources = source_numbers(tool_outputs, question)
    # only big numbers are worth differencing; keeps this O(n^2) on a small set
    big = sorted(n for n in sources if n >= 100)
    differences = {abs(a - b) for a, b in combinations(big, 2)}

    checked = [n for n in extract_numbers(answer) if n >= MIN_CHECKED]
    ungrounded = [
        n
        for n in checked
        if not any(_close(n, s) for s in sources) and not any(_close(n, d) for d in differences)
    ]
    return GroundingResult(checked=len(checked), ungrounded=ungrounded)
