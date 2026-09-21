from datetime import datetime
from typing import Any, Dict
from app.graph.state import GraphState, create_step


def healing_node(state: GraphState) -> GraphState:
    """
    Self-Healing Sub-Agent:
    Parses validation error tracebacks, diagnoses root cause (AST syntax error,
    schema mismatch, safety violation), and synthesizes actionable repair directives.
    """
    history = list(state.get("history", []))
    healing_history = list(state.get("healing_history", []))
    retry_count = state.get("retry_count", 0) + 1
    max_retries = state.get("max_retries", 3)
    error_trace = state.get("error_trace", "Unknown error")
    artifacts = state.get("artifacts", {})
    artifact_type = artifacts.get("artifact_type", "python")
    content = artifacts.get("content", "")
    val_results = state.get("validation_results", {})
    val_details = val_results.get("details", {})

    state["retry_count"] = retry_count

    # Diagnose error and formulate patch directive
    diagnosis = ""
    patch_directive = ""

    if artifact_type == "python":
        if "SyntaxError" in error_trace:
            failed_line = val_details.get("failed_line", "")
            lineno = val_details.get("lineno", 1)
            msg = val_details.get("msg", "invalid syntax")
            if "expected ':'" in msg.lower() or (failed_line and not failed_line.endswith(":")):
                diagnosis = f"Python AST failure at line {lineno}: Function or block statement omitted closing colon (:)."
                patch_directive = "Append ':' to def/if/for/while header and ensure standard 4-space indentation block."
            elif "unclosed" in msg.lower():
                diagnosis = f"Python AST failure at line {lineno}: Unclosed parenthesis, bracket, or string literal."
                patch_directive = "Balance and close all parenthesis pairs and quote delimiters."
            else:
                diagnosis = f"Python AST syntax error at line {lineno}: {msg}."
                patch_directive = "Reconstruct Python syntax according to PEP 8 grammar specifications."
        elif "Security policy" in error_trace:
            diagnosis = "Security policy violation: Prohibited import or dangerous execution call detected."
            patch_directive = "Eliminate dangerous OS/process calls and rewrite using pure in-memory logic."
        else:
            diagnosis = f"AST validation issue: {error_trace}"
            patch_directive = "Refactor code structure to satisfy validator checks."

    elif artifact_type == "sql":
        if "safety violation" in error_trace.lower():
            diagnosis = "SQL safety violation: Attempted write or mutating operation."
            patch_directive = "Rewrite query as a purely read-only SELECT statement with aggregate calculations."
        elif "unknown table" in error_trace.lower():
            diagnosis = "SQL schema error: Query referenced nonexistent table."
            patch_directive = "Target verified database tables: 'customers', 'transactions', 'products', 'system_metrics'."
        else:
            diagnosis = f"SQL error: {error_trace}"
            patch_directive = "Correct SQL syntax and column bindings against database schema."

    else:
        diagnosis = f"API validation issue: {error_trace}"
        patch_directive = "Verify URL scheme (https://) and endpoint path specifications."

    fix_record = {
        "attempt": retry_count,
        "max_retries": max_retries,
        "artifact_type": artifact_type,
        "error": error_trace,
        "diagnosis": diagnosis,
        "fix_applied": patch_directive,
        "timestamp": datetime.utcnow().isoformat()
    }
    healing_history.append(fix_record)
    state["healing_history"] = healing_history

    thought = (
        f"[Self-Healing Engine - Attempt {retry_count}/{max_retries}] "
        f"Diagnosed root cause: {diagnosis}. Directive: {patch_directive}"
    )

    history.append(create_step(
        node="healing",
        action="self_heal_patch",
        thought=thought,
        status="healing",
        details=fix_record
    ))

    state["history"] = history
    state["status"] = "healing"
    return state
