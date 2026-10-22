# 0001 - Explicit LangGraph graph instead of a prebuilt agent

Status: accepted (2026-10)

## Context

LangGraph's `create_react_agent` gives a working tool-calling agent in one line. It hides the
nodes, though, and later work needs to hook into them: a planner step, guardrails before the
answer, tracing per node.

## Decision

Build the graph by hand in `agent/graph.py`: an `agent` node, a `ToolNode`, and
`tools_condition` routing between them. Cap model calls with LangGraph's recursion limit and
return a clear "out of steps" answer instead of raising.

## Consequences

- About 30 more lines than the prebuilt version.
- Each node can be tested with a scripted model (`tests/agent/test_graph.py`).
- Adding a node (planner, answer checker) is a local change to one file.
