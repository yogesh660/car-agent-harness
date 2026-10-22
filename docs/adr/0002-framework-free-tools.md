# 0002 - Tools are plain Python, not LangChain tools

Status: accepted (2026-10)

## Context

Agent frameworks change fast. If tool logic lives inside `@tool` functions, every framework
upgrade risks the business logic, and testing a tool needs the whole framework.

## Decision

Each tool in `src/car_agent/tools/` is a function `(sqlite3.Connection, InputModel) -> OutputModel`
with pydantic models for input and output. No langchain or langgraph imports there. The registry
(`TOOLS`) holds name, description and input model. `agent/tools.py` wraps them as LangChain
`StructuredTool`s.

## Consequences

- Tools are tested with plain pytest, fast and without an LLM stack.
- Switching to another framework (or serving tools over MCP) only touches `agent/`.
- Input models double as the JSON schema the model sees, so field descriptions matter.
  `tests/test_harness.py` enforces that every field has one.
