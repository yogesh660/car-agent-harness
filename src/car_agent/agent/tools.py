"""Wrap the registry tools as LangChain tools for the graph."""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from car_agent.db import connect_readonly
from car_agent.tools import TOOLS, ToolSpec, run_tool


def _as_langchain_tool(spec: ToolSpec, db_path: Path) -> BaseTool:
    def call(**kwargs: Any) -> str:
        # new connection per call, cheap for sqlite and keeps tools thread-safe
        with closing(connect_readonly(db_path)) as conn:
            return json.dumps(run_tool(spec.name, conn, kwargs), ensure_ascii=False)

    return StructuredTool.from_function(
        func=call,
        name=spec.name,
        description=spec.description,
        args_schema=spec.input_model,
    )


def build_tools(db_path: Path) -> list[BaseTool]:
    return [_as_langchain_tool(spec, db_path) for spec in TOOLS]
