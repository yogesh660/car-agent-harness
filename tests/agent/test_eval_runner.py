"""The eval runner end to end, with a scripted model instead of a real one."""

import json

import pytest

pytest.importorskip("langgraph")

from car_agent.agent.graph import build_graph
from car_agent.agent.tools import build_tools
from car_agent.config import Settings
from evals import run as runner
from tests.agent.scripted import call, reply, scripted

CASE = {
    "id": "price-listing",
    "category": "price",
    "question": "Is listing #42 a good deal?",
    "expected_tools": ["estimate_price"],
    "expected_args": {"estimate_price": {"listing_id": 42}},
    "answer_mentions": [42],
}


@pytest.fixture
def settings(db_path):
    return Settings(db_path=db_path, model="fake", base_url=None, max_steps=4)


def run(settings, *script):
    graph = build_graph(scripted(*script), build_tools(settings.db_path))
    return runner.run_case(graph, CASE, settings, judge=None)


def test_good_answer_passes_and_is_grounded(settings):
    row = run(
        settings,
        call("estimate_price", {"listing_id": 42}),
        reply("Listing #42 asks 20,600, the estimate is 20,250, so it is a fair price."),
    )
    assert row["passed"]
    assert row["grounded"]


def test_invented_price_fails_grounding_but_not_tool_scoring(settings):
    row = run(
        settings,
        call("estimate_price", {"listing_id": 42}),
        reply("Listing #42 is worth about 31,000."),
    )
    assert row["passed"]
    assert not row["grounded"]
    assert row["ungrounded_numbers"] == [31000]


def test_provider_error_is_recorded_not_raised(settings):
    class Boom:
        def invoke(self, *a, **k):
            raise TimeoutError("provider timed out")

    row = runner.run_case(Boom(), CASE, settings, judge=None)
    assert not row["passed"]
    assert "TimeoutError" in row["error"]


def test_summary_and_gate(tmp_path, monkeypatch):
    rows = [
        {
            "category": "price",
            "passed": True,
            "tools_ok": True,
            "args_ok": True,
            "grounded": True,
            "seconds": 1.0,
        },
        {
            "category": "search",
            "passed": False,
            "tools_ok": True,
            "args_ok": False,
            "grounded": True,
            "seconds": 3.0,
        },
    ]
    metrics = runner.summarise(rows)
    assert metrics["pass_rate"] == 0.5
    assert metrics["pass_rate.price"] == 1.0
    assert metrics["grounded_rate"] == 1.0

    baseline = tmp_path / "baseline.json"
    monkeypatch.setattr(runner, "BASELINE", baseline)
    assert runner.check_gate(metrics, "full", min_pass=0.0, max_drop=0.05) == []

    baseline.write_text(json.dumps({"full": {"metrics": {"pass_rate": 0.8}}}))
    problems = runner.check_gate(metrics, "full", min_pass=0.0, max_drop=0.05)
    assert len(problems) == 1
    assert "baseline" in problems[0]
    # a different suite has its own baseline
    assert runner.check_gate(metrics, "smoke", min_pass=0.0, max_drop=0.05) == []


def test_mlflow_logging(tmp_path, monkeypatch):
    mlflow = pytest.importorskip("mlflow")
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")
    from evals.tracking import fingerprints, log_run

    params = {"model": "fake", **fingerprints("{}")}
    run_id = log_run(params, {"pass_rate": 0.5}, [{"case_id": "x"}])
    logged = mlflow.get_run(run_id)
    assert logged.data.metrics["pass_rate"] == 0.5
    assert logged.data.params["prompt_sha"] == params["prompt_sha"]
