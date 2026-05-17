"""LangGraph state graph builder and routing logic."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.services.agent_runtime.nodes import (
    context_node,
    human_review_node,
    llm_node,
    tool_node,
)
from app.services.agent_runtime.state import AgentState


def _route_after_llm(state: AgentState) -> str:
    """Decide where to go after LLM node."""
    # Check step limit
    if state.get("step_count", 0) >= state.get("max_steps", 25):
        return "finish"

    # Check for tool calls
    pending = state.get("pending_tool_calls")
    if not pending:
        return "finish"

    # Has tool calls — check if human approval required
    if state.get("require_human_approval", False):
        return "human_review"

    return "tools"


def _route_after_human_review(state: AgentState) -> str:
    """After human review, either execute tools or go back to LLM."""
    decision = state.get("human_decision", {})
    if isinstance(decision, dict) and decision.get("approved") is False:
        # Rejected — go back to LLM with rejection message
        return "llm"
    return "tools"


def build_agent_graph() -> StateGraph:
    """Build the LangGraph agent state graph.

    Flow::

        START → context → llm → (tools? / human_review? / finish)
                                   ↓           ↓
                                 tools  ← human_review
                                   ↓
                                  llm  (loop)
    """
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("context", context_node)
    graph.add_node("llm", llm_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("tools", tool_node)

    # Edges
    graph.add_edge(START, "context")
    graph.add_edge("context", "llm")

    graph.add_conditional_edges(
        "llm",
        _route_after_llm,
        {
            "finish": END,
            "tools": "tools",
            "human_review": "human_review",
        },
    )

    graph.add_conditional_edges(
        "human_review",
        _route_after_human_review,
        {
            "tools": "tools",
            "llm": "llm",
        },
    )

    graph.add_edge("tools", "llm")

    return graph
