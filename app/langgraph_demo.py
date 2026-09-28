from __future__ import annotations

from typing import Any

try:
    from langgraph.graph import END, START, StateGraph  # type: ignore
except ImportError:  # pragma: no cover - runtime environment guard
    END = None
    START = None
    StateGraph = None

from app.tools import get_employee_data


class LangGraphUnavailableError(RuntimeError):
    """Raised when LangGraph is not installed in the current environment."""


def is_langgraph_available() -> bool:
    return StateGraph is not None and START is not None and END is not None


def build_demo_graph() -> Any:
    if not is_langgraph_available():
        raise LangGraphUnavailableError(
            "LangGraph is not installed. Install the actual langgraph package to enable graph execution."
        )

    def agent_node(state: dict[str, Any]) -> dict[str, Any]:
        employee_id = state.get("employee_id")
        if employee_id:
            state["status"] = "employee_selected"
            return state
        state["status"] = "missing_employee_id"
        state["final_answer"] = "I need an employee id before I can look up the employee record."
        return state

    def tool_node(state: dict[str, Any]) -> dict[str, Any]:
        employee_id = state.get("employee_id")
        employee = get_employee_data(employee_id=employee_id)
        state["employee_data"] = employee
        state["final_answer"] = (
            f"Employee {employee.get('employee_name')} is in {employee.get('department')} "
            f"and has an annual salary of {employee.get('annual_salary')}."
        )
        return state

    def route_after_agent(state: dict[str, Any]) -> str:
        if state.get("employee_data"):
            return END
        return "tool"

    graph = StateGraph(dict)
    graph.add_node("agent", agent_node)
    graph.add_node("tool", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tool": "tool", END: END},
    )
    graph.add_edge("tool", "agent")
    return graph.compile()
