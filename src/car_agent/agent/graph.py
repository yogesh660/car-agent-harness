"""The agent graph: model <-> tools loop with a hard step budget.

    START -> agent --(tool calls?)--> tools -> agent ... --(no tool calls)--> END

Written out by hand instead of create_react_agent so every node is visible and testable.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from car_agent.agent.prompts import SYSTEM_PROMPT

OUT_OF_STEPS = "Sorry, I could not finish this within my step budget. Try a narrower question."


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    messages: list[AnyMessage] = field(default_factory=list)
    stopped_early: bool = False
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def tool_outputs(self) -> list[str]:
        """Raw text of every tool result, in order. Used to check answers against."""
        return [_text(m) for m in self.messages if isinstance(m, ToolMessage)]


def build_graph(llm: BaseChatModel, tools: Sequence[BaseTool]) -> Any:
    model = llm.bind_tools(tools)

    def agent(state: AgentState) -> dict[str, list[AnyMessage]]:
        reply = model.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [reply]}

    g = StateGraph(AgentState)
    g.add_node("agent", agent)
    # handle_tool_errors=True: a crashing tool becomes an error message, not a crash
    g.add_node("tools", ToolNode(list(tools), handle_tool_errors=True))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()


def _text(message: AnyMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    # some providers (anthropic) return a list of content blocks
    parts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in content]
    return "".join(parts)


def run_agent(graph: Any, question: str, max_steps: int = 8) -> AgentResult:
    # each model call + tool call is two graph steps
    config = {"recursion_limit": 2 * max_steps}
    try:
        state = graph.invoke({"messages": [HumanMessage(question)]}, config=config)
    except GraphRecursionError:
        return AgentResult(answer=OUT_OF_STEPS, stopped_early=True)

    messages: list[AnyMessage] = state["messages"]
    calls = [
        ToolCall(name=tc["name"], args=tc["args"])
        for m in messages
        if isinstance(m, AIMessage)
        for tc in m.tool_calls
    ]
    ai = [m for m in messages if isinstance(m, AIMessage)]
    # usage_metadata is None for providers/fakes that don't report it
    tokens_in = sum((m.usage_metadata or {}).get("input_tokens", 0) for m in ai)
    tokens_out = sum((m.usage_metadata or {}).get("output_tokens", 0) for m in ai)
    return AgentResult(
        answer=_text(messages[-1]),
        tool_calls=calls,
        messages=messages,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
    )
