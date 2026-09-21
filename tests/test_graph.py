import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.graph.workflow import nexus_graph, execute_workflow_stream
from app.graph.nodes.planner import planner_node
from app.graph.nodes.validator import validate_python_code, validate_sql_query, validate_api_request
from app.tools.database_tool import database_tool
from app.tools.retrieval_tool import retrieval_tool
from app.tools.api_tool import api_tool
from app.core.database import init_db

init_db()
client = TestClient(app)


def test_graph_structure():
    """Verify that the LangGraph StateGraph instance compiles with all required sub-agents."""
    assert nexus_graph is not None
    # Verify nodes are registered in graph
    assert "supervisor" in nexus_graph.nodes
    assert "planner" in nexus_graph.nodes
    assert "synthesizer" in nexus_graph.nodes
    assert "validator" in nexus_graph.nodes
    assert "healing" in nexus_graph.nodes
    assert "executor" in nexus_graph.nodes


def test_planner_decomposition():
    """Verify planner decomposes user task into ordered sub-goals with FAISS retrieval context."""
    initial_state = {
        "task": "Analyze customer transactions and calculate average spend",
        "plan": [],
        "history": []
    }
    planned_state = planner_node(initial_state)
    assert len(planned_state["plan"]) >= 3
    assert planned_state["current_step_index"] == 0
    assert "database" in planned_state["plan"][0].lower() or "schema" in planned_state["plan"][0].lower() or "metadata" in planned_state["plan"][0].lower()
    assert len(planned_state["history"]) > 0


def test_validator_python_ast_success():
    """Verify AST parser validates syntactically correct Python code."""
    valid_code = "def add_numbers(a, b):\n    return a + b\n"
    res = validate_python_code(valid_code)
    assert res["is_valid"] is True
    assert len(res["errors"]) == 0
    assert res["details"]["has_functions"] is True


def test_validator_python_ast_syntax_error():
    """Verify AST parser catches syntax errors (e.g. missing colon)."""
    invalid_code = "def calculate(x)\n    return x * 2\n"
    res = validate_python_code(invalid_code)
    assert res["is_valid"] is False
    assert len(res["errors"]) > 0
    assert "SyntaxError" in res["errors"][0]


def test_validator_python_security_policy():
    """Verify validator blocks dangerous imports like os / subprocess / eval."""
    forbidden_code = "import os\nos.system('echo test')\n"
    res = validate_python_code(forbidden_code)
    assert res["is_valid"] is False
    assert any("Forbidden import 'os'" in err for err in res["errors"])


def test_validator_sql_safety():
    """Verify validator accepts valid SELECT queries and rejects dangerous write operations."""
    valid_sql = "SELECT id, name, email FROM customers WHERE plan = 'Enterprise';"
    res_valid = validate_sql_query(valid_sql)
    assert res_valid["is_valid"] is True

    # Mutating query should fail safety check
    dangerous_sql = "DROP TABLE customers;"
    res_drop = validate_sql_query(dangerous_sql)
    assert res_drop["is_valid"] is False
    assert any("Write operation 'DROP' is strictly prohibited" in err for err in res_drop["errors"])


def test_database_tool_read_only():
    """Verify database tool executes read-only queries and protects tables."""
    import asyncio
    res = asyncio.run(database_tool.execute("SELECT count(*) as total FROM customers"))
    assert res["success"] is True
    assert res["row_count"] > 0
    assert res["rows"][0]["total"] >= 1


def test_retrieval_tool_faiss():
    """Verify in-memory FAISS tool retrieves relevant semantic documents."""
    import asyncio
    res = asyncio.run(retrieval_tool.execute("customers transactions schema", top_k=2))
    assert res["count"] > 0
    assert res["source"] == "faiss_in_memory"


def test_health_endpoint():
    """Verify GET /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "NexusGraph" in data["service"]


def test_tools_catalog_endpoint():
    """Verify GET /api/v1/tools endpoint returns all 3 tools."""
    response = client.get("/api/v1/tools")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    tool_names = [t["name"] for t in data["tools"]]
    assert "retrieval_tool" in tool_names
    assert "database_tool" in tool_names
    assert "api_tool" in tool_names


def test_orchestrate_endpoint_non_streaming():
    """Verify POST /api/v1/orchestrate with stream=False runs and returns state."""
    payload = {
        "task": "Retrieve customer database schema and report table attributes",
        "max_retries": 3,
        "stream": False
    }
    response = client.post("/api/v1/orchestrate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] is not None
    assert data["status"] == "completed"
    assert data["total_steps"] > 0
    assert data["final_output"] is not None

    # Verify state checkpoint endpoint
    state_resp = client.get(f"/api/v1/state/{data['run_id']}")
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["run_id"] == data["run_id"]
    assert len(state_data["checkpoints"]) > 0
