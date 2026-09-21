import pytest
import asyncio
from app.graph.state import GraphState
from app.graph.nodes.healing import healing_node
from app.graph.nodes.validator import validator_node, validate_python_code
from app.graph.nodes.supervisor import supervisor_node
from app.graph.workflow import execute_workflow_stream
from app.core.database import init_db

init_db()


def test_healing_node_ast_syntax_diagnosis():
    """Verify healing node diagnoses missing colon syntax error and prescribes corrective directive."""
    initial_state: GraphState = {
        "task": "Test code repair",
        "artifacts": {
            "artifact_type": "python",
            "content": "def calculate_total(items)\n    return sum(items)\n"
        },
        "validation_results": {
            "is_valid": False,
            "errors": ["SyntaxError at line 1, column 27: expected ':'\n  Code: def calculate_total(items)"],
            "details": {
                "lineno": 1,
                "msg": "expected ':'",
                "failed_line": "def calculate_total(items)"
            }
        },
        "error_trace": "SyntaxError at line 1, column 27: expected ':'\n  Code: def calculate_total(items)",
        "retry_count": 0,
        "max_retries": 3,
        "healing_history": [],
        "history": []
    }

    healed_state = healing_node(initial_state)

    assert healed_state["retry_count"] == 1
    assert len(healed_state["healing_history"]) == 1
    fix = healed_state["healing_history"][0]
    assert "omitted closing colon" in fix["diagnosis"]
    assert "Append ':'" in fix["fix_applied"]
    assert healed_state["status"] == "healing"


def test_healing_max_retries_abort():
    """Verify supervisor aborts with failure state when max healing retries are exhausted."""
    failed_state: GraphState = {
        "task": "Unfixable code task",
        "plan": ["Decomposed step 1"],
        "current_step_index": 0,
        "artifacts": {"artifact_type": "python", "content": "bad code", "step_index": 0},
        "validation_results": {"is_valid": False, "errors": ["Unrecoverable syntax defect"]},
        "retry_count": 3,
        "max_retries": 3,
        "history": []
    }

    routed_state = supervisor_node(failed_state)
    assert routed_state["status"] == "failed"
    assert routed_state["next_node"] == "end"
    assert "Max healing retries" in routed_state["final_output"]


@pytest.mark.asyncio
async def test_full_self_healing_execution_cycle():
    """
    End-to-end integration test:
    Executes a task that induces an intentional syntax error, verifies the
    LangGraph cycle loops through Validator -> Healing -> Synthesizer -> Validator -> Success.
    """
    task = "Synthesize python code with intentional syntax error to test AST validator and self-healing engine"
    events = []

    async for event in execute_workflow_stream(task, max_retries=3):
        events.append(event)

    # Filter node transition events
    node_names = [e.get("node") for e in events if e.get("event") == "node_transition"]

    # Verify that healing node was invoked
    assert "healing" in node_names
    assert "validator" in node_names
    assert "synthesizer" in node_names

    # Check terminal completion event
    completion_event = next((e for e in events if e.get("event") == "run_completed"), None)
    assert completion_event is not None
    assert completion_event["status"] == "completed"

    # Verify that healing history was recorded
    healing_history = completion_event.get("healing_history", [])
    assert len(healing_history) >= 1
    assert healing_history[0]["attempt"] == 1
    assert "colon" in healing_history[0]["diagnosis"].lower()
