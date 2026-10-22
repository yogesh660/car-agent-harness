"""Scoring for eval cases. Pure functions, unit tested in tests/unit/test_eval_scoring.py.

A case passes when:
  - every expected tool was called, and
  - for each tool in expected_args, at least one call has those args (extra args are fine)
  - for cases with no expected tools: no tool was called at all
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from car_agent.schemas import normalize_make


@dataclass
class CaseScore:
    case_id: str
    passed: bool
    missing_tools: list[str]
    arg_mismatches: list[str]
    unexpected_tool_use: bool = False


def _same(key: str, expected: Any, actual: Any) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        if key == "make":
            return normalize_make(expected).lower() == normalize_make(actual).lower()
        return expected.strip().lower() == actual.strip().lower()
    if isinstance(expected, list) and isinstance(actual, list):
        return sorted(expected) == sorted(actual)
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return float(expected) == float(actual)
    return bool(expected == actual)


def _args_match(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    return all(k in actual and _same(k, v, actual[k]) for k, v in expected.items())


def score_case(case: dict[str, Any], calls: list[tuple[str, dict[str, Any]]]) -> CaseScore:
    called = {name for name, _ in calls}

    if not case["expected_tools"]:
        return CaseScore(case["id"], not calls, [], [], unexpected_tool_use=bool(calls))

    missing = [t for t in case["expected_tools"] if t not in called]
    mismatches = []
    for tool, expected in case["expected_args"].items():
        if tool in called and not any(
            _args_match(expected, args) for name, args in calls if name == tool
        ):
            seen = [args for name, args in calls if name == tool]
            mismatches.append(f"{tool}: expected {expected}, got {seen}")

    return CaseScore(case["id"], not missing and not mismatches, missing, mismatches)
