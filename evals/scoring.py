"""Scoring for eval cases. Pure functions, unit tested in tests/unit/test_eval_scoring.py.

A case passes when:
  - every expected tool was called,
  - for each tool in expected_args, at least one call has those args (extra args are fine,
    and an omitted arg counts as matching when the expected value is the tool's default),
  - every listing id in answer_mentions appears in the final answer,
  - for cases with no expected tools: no tool was called at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic_core import PydanticUndefined

from car_agent.schemas import normalize_city, normalize_make
from car_agent.tools import TOOLS_BY_NAME


@dataclass
class CaseScore:
    case_id: str
    passed: bool
    missing_tools: list[str] = field(default_factory=list)
    arg_mismatches: list[str] = field(default_factory=list)
    missing_mentions: list[int] = field(default_factory=list)
    unexpected_tool_use: bool = False

    @property
    def tools_ok(self) -> bool:
        return not self.missing_tools and not self.unexpected_tool_use

    @property
    def args_ok(self) -> bool:
        return self.tools_ok and not self.arg_mismatches


def _same(key: str, expected: Any, actual: Any) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        if key == "make":
            return normalize_make(expected).lower() == normalize_make(actual).lower()
        if key == "city":
            return normalize_city(expected).lower() == normalize_city(actual).lower()
        e, a = expected.strip().lower(), actual.strip().lower()
        if key == "model":
            # "Octavia" and "Octavia Combi" both find the same cars
            return e in a or a in e
        return e == a
    if isinstance(expected, list) and isinstance(actual, list):
        return sorted(expected) == sorted(actual)
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return float(expected) == float(actual)
    return bool(expected == actual)


def _default(tool: str, key: str) -> Any:
    spec = TOOLS_BY_NAME.get(tool)
    if spec is None or key not in spec.input_model.model_fields:
        return PydanticUndefined
    return spec.input_model.model_fields[key].default


def _args_match(tool: str, expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    for key, value in expected.items():
        if key in actual and actual[key] is not None:
            if not _same(key, value, actual[key]):
                return False
        elif _default(tool, key) != value:
            return False
    return True


def _mentions(answer: str, listing_id: int) -> bool:
    return re.search(rf"(?<![\d.,]){listing_id}(?![\d]|[.,]\d)", answer) is not None


def score_case(
    case: dict[str, Any], calls: list[tuple[str, dict[str, Any]]], answer: str = ""
) -> CaseScore:
    called = {name for name, _ in calls}

    if not case["expected_tools"]:
        return CaseScore(case["id"], passed=not calls, unexpected_tool_use=bool(calls))

    missing = [t for t in case["expected_tools"] if t not in called]
    mismatches = []
    for tool, expected in case["expected_args"].items():
        seen = [args for name, args in calls if name == tool]
        if seen and not any(_args_match(tool, expected, args) for args in seen):
            mismatches.append(f"{tool}: expected {expected}, got {seen}")

    not_mentioned = [i for i in case.get("answer_mentions", []) if not _mentions(answer, i)]

    return CaseScore(
        case["id"],
        passed=not missing and not mismatches and not not_mentioned,
        missing_tools=missing,
        arg_mismatches=mismatches,
        missing_mentions=not_mentioned,
    )
