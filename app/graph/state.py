from typing import Any, Dict, List, Optional, TypedDict
from datetime import datetime


class AgentStep(TypedDict, total=False):
    step_id: int
    node: str
    action: str
    thought: str
    status: str          # "running", "success", "warning", "error", "healing"
    details: Dict[str, Any]
    timestamp: str


class GraphState(TypedDict, total=False):
    task: str
    run_id: str
    plan: List[str]
    current_step_index: int
    current_subgoal: Optional[str]
    artifacts: Dict[str, Any]           # {"code": ..., "sql": ..., "artifact_type": "python"|"sql"|"api"}
    tool_results: Dict[str, Any]        # {"retrieval": ..., "database": ..., "api": ...}
    validation_results: Dict[str, Any]  # {"is_valid": bool, "errors": list[str], "details": dict}
    error_trace: Optional[str]          # traceback or validation failure description
    healing_history: List[Dict[str, Any]]
    retry_count: int
    max_retries: int
    final_output: Optional[str]
    status: str                         # "initialized", "planning", "synthesizing", "validating", "healing", "executing", "completed", "failed"
    history: List[AgentStep]
    next_node: Optional[str]


def create_step(node: str, action: str, thought: str, status: str = "success", details: Optional[Dict[str, Any]] = None) -> AgentStep:
    """Helper to produce a structured AgentStep log item."""
    return {
        "step_id": 0,  # Will be assigned or incremented
        "node": node,
        "action": action,
        "thought": thought,
        "status": status,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat()
    }
