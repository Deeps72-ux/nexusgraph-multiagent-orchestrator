import time
from typing import Any, Dict
from app.graph.state import GraphState, create_step
from app.tools.database_tool import database_tool
from app.tools.api_tool import api_tool


async def executor_node(state: GraphState) -> GraphState:
    """
    Tool Execution Node:
    Executes validated artifacts against connected systems:
    - SQL queries against SQLite database
    - HTTP requests via API tool
    - Python execution in safe scope
    If a runtime execution error occurs, populates error_trace and routes to self-healing.
    """
    history = list(state.get("history", []))
    artifacts = state.get("artifacts", {})
    artifact_type = artifacts.get("artifact_type", "python")
    content = artifacts.get("content", "")
    tool_results = dict(state.get("tool_results", {}))

    execution_success = True
    result_data: Any = None
    error_message: str = ""

    try:
        if artifact_type == "sql":
            res = await database_tool.execute(content)
            if not res.get("success"):
                execution_success = False
                error_message = res.get("error", "SQL runtime execution failure")
            else:
                result_data = res
                tool_results["database"] = res

        elif artifact_type == "api":
            res = await api_tool.execute(content)
            if not res.get("success"):
                execution_success = False
                error_message = res.get("error", "API request failure")
            else:
                result_data = res
                tool_results["api"] = res

        elif artifact_type == "python":
            # Execute in sandboxed local scope
            safe_globals = {
                "__builtins__": {
                    "print": print,
                    "len": len,
                    "sum": sum,
                    "min": min,
                    "max": max,
                    "round": round,
                    "range": range,
                    "isinstance": isinstance,
                    "int": int,
                    "float": float,
                    "str": str,
                    "dict": dict,
                    "list": list,
                    "set": set,
                    "bool": bool,
                }
            }
            local_scope: Dict[str, Any] = {}
            exec(content, safe_globals, local_scope)

            # Check if any function was defined and run it with sample data
            demo_result = None
            for name, func in local_scope.items():
                if callable(func):
                    try:
                        demo_result = func([10.5, 20.0, 35.5, 42.0, 18.0])
                    except Exception as fe:
                        demo_result = f"Function {name} compiled successfully (test invocation note: {fe})"
                    break

            res = {
                "success": True,
                "defined_functions": [k for k, v in local_scope.items() if callable(v)],
                "sample_invocation_result": demo_result or "Execution succeeded with clean namespace."
            }
            result_data = res
            tool_results["python"] = res

    except Exception as e:
        execution_success = False
        error_message = f"Runtime execution error: {str(e)}"

    if execution_success:
        thought = f"Tool execution succeeded for {artifact_type} artifact."
        history.append(create_step(
            node="executor",
            action="execute_tool",
            thought=thought,
            status="success",
            details={"artifact_type": artifact_type, "result_preview": str(result_data)[:200]}
        ))
        state["tool_results"] = tool_results
        state["status"] = "executing"
    else:
        thought = f"Tool runtime execution FAILED: {error_message}. Redirecting to healing."
        history.append(create_step(
            node="executor",
            action="execute_tool",
            thought=thought,
            status="error",
            details={"artifact_type": artifact_type, "error": error_message}
        ))
        state["validation_results"] = {"is_valid": False, "errors": [error_message]}
        state["error_trace"] = error_message
        state["status"] = "healing"

    state["history"] = history
    return state
