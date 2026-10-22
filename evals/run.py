"""Run the agent on evals/cases.jsonl with the configured model and score tool use.

    CAR_AGENT_MODEL=ollama:qwen2.5:7b python -m evals.run
    python -m evals.run --only price-asking --min-pass 1.0

Writes evals/results/latest.json and exits 1 if the pass rate is below --min-pass,
so the same command works as a gate in CI once a model endpoint is available there.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from car_agent.agent.graph import build_graph, run_agent
from car_agent.agent.llm import load_chat_model
from car_agent.agent.tools import build_tools
from car_agent.config import Settings
from car_agent.data.seed import seed_database
from evals.scoring import score_case

HERE = Path(__file__).parent


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=HERE / "cases.jsonl")
    parser.add_argument("--only", nargs="*", help="run only these case ids")
    parser.add_argument("--min-pass", type=float, default=0.8)
    args = parser.parse_args()

    settings = Settings.from_env()
    if not settings.db_path.exists():
        seed_database(settings.db_path)

    cases = load_cases(args.cases)
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]

    graph = build_graph(
        load_chat_model(settings.model, settings.base_url), build_tools(settings.db_path)
    )

    results = []
    for case in cases:
        start = time.perf_counter()
        out = run_agent(graph, case["question"], max_steps=settings.max_steps)
        score = score_case(case, [(c.name, c.args) for c in out.tool_calls])
        took = time.perf_counter() - start

        mark = "PASS" if score.passed else "FAIL"
        print(f"{mark}  {case['id']:<28} {took:5.1f}s")
        for problem in score.missing_tools:
            print(f"      missing tool: {problem}")
        for problem in score.arg_mismatches:
            print(f"      {problem}")
        if score.unexpected_tool_use:
            print("      called tools when none were needed")

        results.append({**asdict(score), "seconds": round(took, 2), "answer": out.answer})

    pass_rate = sum(r["passed"] for r in results) / max(len(results), 1)
    print(f"\n{sum(r['passed'] for r in results)}/{len(results)} passed ({pass_rate:.0%})")

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "latest.json").write_text(
        json.dumps({"model": settings.model, "pass_rate": pass_rate, "cases": results}, indent=2)
    )
    return 0 if pass_rate >= args.min_pass else 1


if __name__ == "__main__":
    sys.exit(main())
