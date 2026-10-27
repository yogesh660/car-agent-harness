"""Run the agent on evals/cases.jsonl and score it.

    make eval                                  full set, configured model
    make eval-smoke                            13 smoke cases, used on PRs
    uv run python -m evals.run --judge         add the LLM-as-judge faithfulness check
    uv run python -m evals.run --only price-asking compare-two

Writes evals/results/latest.json. Exits 1 when the pass rate is below --min-pass or more
than --max-drop below evals/baseline.json, so the same command is the CI gate.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from car_agent.agent.graph import build_graph, run_agent
from car_agent.agent.llm import load_chat_model
from car_agent.agent.tools import build_tools
from car_agent.config import Settings
from car_agent.data.seed import seed_database
from evals.grounding import check_grounding
from evals.scoring import score_case
from evals.tracking import fingerprints

HERE = Path(__file__).parent
BASELINE = HERE / "baseline.json"
GATED = ("pass_rate", "grounded_rate")


def load_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_case(graph: Any, case: dict[str, Any], settings: Settings, judge: Any) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        out = run_agent(graph, case["question"], max_steps=settings.max_steps)
    except Exception as exc:  # provider errors, timeouts: record and keep going
        return {
            "case_id": case["id"],
            "category": case["category"],
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "seconds": round(time.perf_counter() - start, 2),
        }
    took = time.perf_counter() - start

    calls = [(c.name, c.args) for c in out.tool_calls]
    score = score_case(case, calls, out.answer)
    grounding = check_grounding(out.answer, out.tool_outputs, case["question"])
    row: dict[str, Any] = {
        **asdict(score),
        "category": case["category"],
        "tools_ok": score.tools_ok,
        "args_ok": score.args_ok,
        "grounded": grounding.grounded,
        "ungrounded_numbers": grounding.ungrounded,
        "stopped_early": out.stopped_early,
        "tool_calls": [{"name": n, "args": a} for n, a in calls],
        "answer": out.answer,
        "seconds": round(took, 2),
        "input_tokens": out.input_tokens,
        "output_tokens": out.output_tokens,
    }
    if judge is not None:
        from evals.judge import judge_answer

        verdict = judge_answer(judge, case["question"], out.tool_outputs, out.answer)
        row["judge"] = verdict.model_dump()
    return row


def summarise(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = max(len(rows), 1)
    ok = [r for r in rows if "error" not in r]
    secs = sorted(r["seconds"] for r in ok) or [0.0]
    metrics: dict[str, float] = {
        "cases": len(rows),
        "pass_rate": sum(r["passed"] for r in rows) / n,
        "tool_accuracy": sum(r.get("tools_ok", False) for r in rows) / n,
        "arg_accuracy": sum(r.get("args_ok", False) for r in rows) / n,
        "grounded_rate": sum(r.get("grounded", False) for r in rows) / n,
        "errors": len(rows) - len(ok),
        "stopped_early": sum(r.get("stopped_early", False) for r in ok),
        "latency_p50_s": statistics.median(secs),
        "latency_p95_s": secs[min(len(secs) - 1, round(0.95 * (len(secs) - 1)))],
        "tokens_per_case": sum(r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in ok)
        / max(len(ok), 1),
    }
    judged = [r["judge"] for r in ok if "judge" in r and not r["judge"]["error"]]
    if judged:
        metrics["judge_supported_rate"] = sum(j["supported"] for j in judged) / len(judged)

    by_cat: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r["passed"])
    for cat, results in sorted(by_cat.items()):
        metrics[f"pass_rate.{cat}"] = sum(results) / len(results)
    return metrics


def check_gate(
    metrics: dict[str, float], suite: str, min_pass: float, max_drop: float
) -> list[str]:
    problems = []
    if metrics["pass_rate"] < min_pass:
        problems.append(f"pass_rate {metrics['pass_rate']:.0%} below minimum {min_pass:.0%}")
    if BASELINE.exists():
        base = json.loads(BASELINE.read_text()).get(suite, {}).get("metrics", {})
        for key in GATED:
            if key in base and metrics[key] < base[key] - max_drop:
                problems.append(
                    f"{key} {metrics[key]:.0%} dropped more than {max_drop:.0%} "
                    f"below baseline {base[key]:.0%}"
                )
    return problems


def write_baseline(suite: str, metrics: dict[str, float], params: dict[str, Any]) -> None:
    data = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    data[suite] = {
        "metrics": {k: round(metrics[k], 4) for k in GATED},
        "model": params["model"],
        "prompt_sha": params["prompt_sha"],
        "tools_sha": params["tools_sha"],
        "date": datetime.now(UTC).date().isoformat(),
    }
    BASELINE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"baseline for '{suite}' written to {BASELINE}")


def report_to_github(suite: str, metrics: dict[str, float], problems: list[str]) -> None:
    """Job summary table + a notice annotation (annotations are readable via the public API)."""
    headline = (
        f"{suite}: pass {metrics['pass_rate']:.0%}, tools {metrics['tool_accuracy']:.0%}, "
        f"args {metrics['arg_accuracy']:.0%}, grounded {metrics['grounded_rate']:.0%}"
    )
    if "judge_supported_rate" in metrics:
        headline += f", judge {metrics['judge_supported_rate']:.0%}"
    level = "error" if problems else "notice"
    print(f"::{level} title=car-agent eval::{headline}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    lines = [f"## Eval: {suite}", "", "| metric | value |", "|---|---|"]
    for key, value in metrics.items():
        shown = f"{value:.0%}" if "rate" in key or "accuracy" in key else f"{value:g}"
        lines.append(f"| {key} | {shown} |")
    lines += ["", *[f"- :x: {p}" for p in problems]]
    with open(summary, "a") as fh:
        fh.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cases", type=Path, default=HERE / "cases.jsonl")
    parser.add_argument("--only", nargs="*", help="run only these case ids")
    parser.add_argument("--smoke", action="store_true", help="only cases marked smoke")
    parser.add_argument("--judge", action="store_true", help="add LLM-as-judge check")
    parser.add_argument("--min-pass", type=float, default=0.0)
    parser.add_argument("--max-drop", type=float, default=0.05)
    parser.add_argument("--delay", type=float, default=0.0, help="seconds between cases")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--mlflow", action="store_true", help="log the run to MLflow")
    args = parser.parse_args()

    settings = Settings.from_env()
    if not settings.db_path.exists():
        seed_database(settings.db_path)

    cases_text = args.cases.read_text()
    cases = load_cases(args.cases)
    suite = "smoke" if args.smoke else "full"
    if args.smoke:
        cases = [c for c in cases if c.get("smoke")]
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]
        suite = "custom"

    llm = load_chat_model(settings.model, settings.base_url)
    graph = build_graph(llm, build_tools(settings.db_path))
    judge = None
    if args.judge:
        judge_model = os.environ.get("CAR_AGENT_JUDGE_MODEL", settings.model)
        judge = load_chat_model(judge_model, os.environ.get("CAR_AGENT_JUDGE_BASE_URL"))

    rows = []
    for i, case in enumerate(cases):
        if i and args.delay:
            time.sleep(args.delay)
        row = run_case(graph, case, settings, judge)
        rows.append(row)

        mark = "PASS" if row["passed"] else "FAIL"
        print(f"{mark}  {case['id']:<32} {row['seconds']:5.1f}s")
        if "error" in row:
            print(f"      error: {row['error']}")
            continue
        for tool in row["missing_tools"]:
            print(f"      missing tool: {tool}")
        for problem in row["arg_mismatches"]:
            print(f"      {problem}")
        if row["missing_mentions"]:
            print(f"      answer does not mention listing(s) {row['missing_mentions']}")
        if row["unexpected_tool_use"]:
            print("      called tools when none were needed")
        if row["ungrounded_numbers"]:
            print(f"      numbers not backed by tool results: {row['ungrounded_numbers']}")
        if "judge" in row and not row["judge"]["supported"] and not row["judge"]["error"]:
            print(f"      judge: {row['judge']['unsupported_claims']}")

    metrics = summarise(rows)
    params = {"model": settings.model, "suite": suite, "judge": args.judge}
    params |= fingerprints(cases_text)

    print()
    for key, value in metrics.items():
        shown = f"{value:.0%}" if "rate" in key or "accuracy" in key else f"{value:g}"
        print(f"{key:<28} {shown}")

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "latest.json").write_text(
        json.dumps({"params": params, "metrics": metrics, "cases": rows}, indent=2)
    )

    if args.mlflow or os.environ.get("MLFLOW_TRACKING_URI"):
        import mlflow

        from evals.tracking import log_run

        if not os.environ.get("MLFLOW_TRACKING_URI"):
            mlflow.set_tracking_uri("sqlite:///mlflow.db")  # same store `make mlflow` opens

        run_id = log_run(params, metrics, rows, tags={"git_sha": os.environ.get("GITHUB_SHA", "")})
        print(f"\nlogged to MLflow run {run_id}")

    if args.write_baseline and suite != "custom":
        write_baseline(suite, metrics, params)

    problems = [] if suite == "custom" else check_gate(metrics, suite, args.min_pass, args.max_drop)
    if os.environ.get("GITHUB_ACTIONS"):
        report_to_github(suite, metrics, problems)
    for problem in problems:
        print(f"GATE: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
