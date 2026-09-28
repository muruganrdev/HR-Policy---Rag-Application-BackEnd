from app.langgraph_demo import build_demo_graph, is_langgraph_available


def test_langgraph_demo_builds_and_runs():
    assert is_langgraph_available() is True
    graph = build_demo_graph()
    result = graph.invoke({"employee_id": "005"})
    assert result["employee_data"]["employee_id"] == "005"
    assert "employee_name" in result["employee_data"]
    assert "final_answer" in result
    assert "Employee" in result["final_answer"]
    assert result["status"] == "employee_selected"
