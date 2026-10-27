"""Graph tests with a scripted fake model: no API key, no network, fully deterministic.

They check the wiring (tool calls reach the tools, results flow back, errors don't crash,
the step budget holds), not answer quality. Answer quality is what evals/ is for.
"""

import json
from itertools import count

import pytest

pytest.importorskip("langgraph")

from langchain_core.messages import AIMessage, ToolMessage

from car_agent.agent.graph import OUT_OF_STEPS, build_graph, run_agent
from car_agent.agent.tools import build_tools
from tests.agent.scripted import ScriptedModel, call


def test_search_then_answer(db_path):
    model = ScriptedModel(
        messages=iter(
            [
                call(
                    "search_listings", {"fuel": "diesel", "body": "estate", "max_price_eur": 15000}
                ),
                AIMessage(content="Found some diesel estates."),
            ]
        )
    )
    result = run_agent(build_graph(model, build_tools(db_path)), "cheap diesel estate?")

    assert result.answer == "Found some diesel estates."
    assert [c.name for c in result.tool_calls] == ["search_listings"]
    assert not result.stopped_early

    tool_msg = next(m for m in result.messages if isinstance(m, ToolMessage))
    payload = json.loads(tool_msg.content)
    assert payload["total_matches"] > 0
    assert all(car["fuel"] == "diesel" for car in payload["listings"])


def test_two_tools_in_sequence(db_path):
    model = ScriptedModel(
        messages=iter(
            [
                call("search_listings", {"model": "Golf", "limit": 2}, "c1"),
                call("estimate_price", {"listing_id": 1}, "c2"),
                AIMessage(content="done"),
            ]
        )
    )
    result = run_agent(build_graph(model, build_tools(db_path)), "q")
    assert [c.name for c in result.tool_calls] == ["search_listings", "estimate_price"]


def test_bad_tool_args_do_not_crash_the_graph(db_path):
    model = ScriptedModel(
        messages=iter(
            [
                call("search_listings", {"fuel": "steam"}),
                AIMessage(content="Sorry, unknown fuel type."),
            ]
        )
    )
    result = run_agent(build_graph(model, build_tools(db_path)), "steam cars?")

    tool_msg = next(m for m in result.messages if isinstance(m, ToolMessage))
    assert "fuel" in str(tool_msg.content).lower()
    assert result.answer == "Sorry, unknown fuel type."


def test_step_budget_stops_a_looping_model(db_path):
    ids = count()

    def forever():
        while True:
            yield call("search_listings", {}, f"c{next(ids)}")

    model = ScriptedModel(messages=forever())
    result = run_agent(build_graph(model, build_tools(db_path)), "loop", max_steps=3)

    assert result.stopped_early
    assert result.answer == OUT_OF_STEPS


def test_tokens_and_tool_outputs_are_collected(db_path):
    usage = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    model = ScriptedModel(
        messages=iter(
            [
                call("estimate_price", {"listing_id": 42}, usage=usage),
                AIMessage(content="Fair price.", usage_metadata=usage),
            ]
        )
    )
    result = run_agent(build_graph(model, build_tools(db_path)), "is #42 a good deal?")

    assert result.input_tokens == 200
    assert result.output_tokens == 40
    assert len(result.tool_outputs) == 1
    assert json.loads(result.tool_outputs[0])["verdict"] in ("below_market", "fair", "above_market")
