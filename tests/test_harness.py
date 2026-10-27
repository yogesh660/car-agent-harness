"""Checks on the repo itself, not on the product.

These keep the repo safe to hand to a coding agent: docs that point at real commands,
every tool tested, every tool described well enough for a model to use it.
If one of these fails, the fix is usually in docs or tests, not in src/.
"""

import json
import re
from pathlib import Path

import pytest

from car_agent.tools import TOOLS, TOOLS_BY_NAME

ROOT = Path(__file__).resolve().parents[1]


def makefile_targets() -> set[str]:
    text = (ROOT / "Makefile").read_text()
    return set(re.findall(r"^([a-z-]+):", text, flags=re.MULTILINE))


def test_make_targets_in_claude_md_exist():
    mentioned = set(re.findall(r"`make ([a-z-]+)", (ROOT / "CLAUDE.md").read_text()))
    assert mentioned, "CLAUDE.md should tell agents which make targets to run"
    missing = mentioned - makefile_targets()
    assert not missing, f"CLAUDE.md mentions targets the Makefile does not have: {missing}"


def test_agents_md_points_to_claude_md():
    assert "CLAUDE.md" in (ROOT / "AGENTS.md").read_text()


@pytest.mark.parametrize("spec", TOOLS, ids=lambda s: s.name)
def test_every_tool_has_its_own_test_file(spec):
    path = ROOT / "tests" / "unit" / f"test_{spec.name}.py"
    assert path.exists(), f"add {path.relative_to(ROOT)} for the new tool"


@pytest.mark.parametrize("spec", TOOLS, ids=lambda s: s.name)
def test_every_tool_argument_is_described(spec):
    # the model only sees the JSON schema, so an undescribed field is a guess for it
    props = spec.input_model.model_json_schema()["properties"]
    undocumented = [name for name, p in props.items() if not p.get("description")]
    assert not undocumented, f"{spec.name}: add Field(description=...) for {undocumented}"


@pytest.mark.parametrize("spec", TOOLS, ids=lambda s: s.name)
def test_tool_names_and_descriptions(spec):
    assert re.fullmatch(r"[a-z][a-z_]+", spec.name)
    assert len(spec.description) >= 40


CATEGORIES = {
    "search",
    "search_complex",
    "normalization",
    "price",
    "compare",
    "multi_step",
    "not_found",
    "vague",
    "out_of_scope",
}
CASE_KEYS = {
    "id",
    "category",
    "question",
    "expected_tools",
    "expected_args",
    "answer_mentions",
    "smoke",
}


def load_cases():
    lines = (ROOT / "evals" / "cases.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_eval_cases_are_valid():
    cases = load_cases()
    assert len(cases) >= 50

    seen = set()
    for case in cases:
        assert case["id"] not in seen, f"duplicate eval id {case['id']}"
        seen.add(case["id"])
        assert set(case) <= CASE_KEYS, f"{case['id']}: unknown keys {set(case) - CASE_KEYS}"
        assert case["category"] in CATEGORIES, f"{case['id']}: unknown category"
        assert case["question"].strip()
        for name in case["expected_args"]:
            assert name in case["expected_tools"], f"{case['id']}: args for unlisted tool"
        for name in case["expected_tools"]:
            assert name in TOOLS_BY_NAME, f"{case['id']}: unknown tool {name}"
        for name, args in case["expected_args"].items():
            # catches typos like "max_price" before they silently fail an eval run
            TOOLS_BY_NAME[name].input_model.model_validate(args)


def test_eval_set_covers_every_tool_and_category():
    cases = load_cases()
    for spec in TOOLS:
        n = sum(spec.name in c["expected_tools"] for c in cases)
        assert n >= 3, f"only {n} eval cases use {spec.name}; add more"
    assert {c["category"] for c in cases} == CATEGORIES

    smoke = [c for c in cases if c.get("smoke")]
    assert 10 <= len(smoke) <= 20, "smoke set runs on PRs; keep it small but meaningful"
    for spec in TOOLS:
        assert any(spec.name in c["expected_tools"] for c in smoke), (
            f"no smoke case for {spec.name}"
        )


def test_listing_ids_in_eval_cases_exist(conn):
    # cases reference seeded ids; this fails if data/seed.py output changes under them
    ids = set()
    for case in load_cases():
        ids.update(case.get("answer_mentions", []))
        for args in case["expected_args"].values():
            ids.update(args.get("listing_ids", []))
            if "listing_id" in args:
                ids.add(args["listing_id"])
    ids.discard(999_999)  # the deliberate not-found case
    placeholders = ",".join("?" * len(ids))
    found = {
        r[0]
        for r in conn.execute(f"SELECT id FROM listings WHERE id IN ({placeholders})", list(ids))
    }
    assert ids == found, f"eval cases reference missing listings: {ids - found}"
