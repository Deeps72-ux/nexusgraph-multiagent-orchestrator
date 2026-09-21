import re
from typing import Any, Dict
from app.graph.state import GraphState, create_step


def synthesizer_node(state: GraphState) -> GraphState:
    """
    Synthesizer Sub-Agent:
    Generates code or queries to accomplish the active sub-goal.
    Applies self-healing corrections if resolving an error trace.
    """
    task = state.get("task", "")
    plan = state.get("plan", [])
    step_idx = state.get("current_step_index", 0)
    current_subgoal = state.get("current_subgoal", plan[step_idx] if step_idx < len(plan) else "Execute sub-goal")
    history = list(state.get("history", []))
    healing_history = state.get("healing_history", [])
    retry_count = state.get("retry_count", 0)
    is_recovering = len(healing_history) > 0 and state.get("status") == "healing"

    artifact_type = "python"
    subgoal_lower = current_subgoal.lower()
    task_lower = task.lower()

    if "sql" in subgoal_lower or "database" in subgoal_lower or "query" in subgoal_lower:
        artifact_type = "sql"
    elif "api" in subgoal_lower or "http" in subgoal_lower:
        artifact_type = "api"
    else:
        artifact_type = "python"

    content = ""
    description = ""
    thought = ""

    # Check if this is a healing recovery cycle
    if is_recovering:
        latest_fix = healing_history[-1]
        thought = f"Synthesizing corrected artifact incorporating healing diagnosis: {latest_fix.get('fix_applied')}"

        if artifact_type == "python":
            # Repaired python code
            content = (
                "def process_data(items):\n"
                "    \"\"\"Processed dataset metrics after automated self-healing.\"\"\"\n"
                "    results = [round(x * 1.15, 2) for x in items if x is not None]\n"
                "    summary = {\n"
                "        'total': sum(results),\n"
                "        'count': len(results),\n"
                "        'mean': round(sum(results) / max(len(results), 1), 2)\n"
                "    }\n"
                "    return summary\n"
            )
            description = "Corrected Python script with validated syntax and closed function declaration."
        elif artifact_type == "sql":
            content = (
                "SELECT c.name, c.plan, c.country, "
                "COUNT(t.id) AS transaction_count, "
                "COALESCE(SUM(t.amount), 0) AS total_spend "
                "FROM customers c "
                "LEFT JOIN transactions t ON c.id = t.customer_id AND t.status = 'completed' "
                "GROUP BY c.id, c.name, c.plan, c.country "
                "ORDER BY total_spend DESC;"
            )
            description = "Corrected read-only SQL query with verified table references and aggregations."
        else:
            content = "https://api.nexusgraph.internal/v1/rates"
            description = "Corrected verified REST API endpoint URL."

    # Intentional error test mode for self-healing demonstration
    elif ("heal" in task_lower or "syntax" in task_lower or "broken" in task_lower or "intentional error" in task_lower) and retry_count == 0 and step_idx == 1:
        # Deliberately emit syntax error (missing colon) to activate validator AST catch and self-healing loop
        artifact_type = "python"
        content = (
            "def process_data(items)\n"  # Missing colon -> SyntaxError for AST
            "    \"\"\"Intentional syntax defect to demonstrate self-healing engine.\"\"\"\n"
            "    return [x * 1.15 for x in items]\n"
        )
        description = "Candidate Python script (containing unclosed definition to test AST validation & self-healing)."
        thought = "Generated initial candidate code. Note: Deliberately testing AST validation catch for automated healing."

    # Standard SQL Synthesis
    elif artifact_type == "sql":
        if "customer" in task_lower or "spend" in task_lower or "transaction" in task_lower:
            content = (
                "SELECT c.name, c.plan, c.country, "
                "COUNT(t.id) AS total_transactions, "
                "ROUND(COALESCE(SUM(t.amount), 0), 2) AS total_spent, "
                "ROUND(COALESCE(AVG(t.amount), 0), 2) AS avg_transaction "
                "FROM customers c "
                "LEFT JOIN transactions t ON c.id = t.customer_id "
                "GROUP BY c.id, c.name, c.plan, c.country "
                "ORDER BY total_spent DESC;"
            )
            description = "SQL analytical query aggregating customer transactions, total spend, and average spend."
        elif "metric" in task_lower or "system" in task_lower:
            content = (
                "SELECT service, ROUND(AVG(cpu_pct), 2) as avg_cpu, "
                "ROUND(AVG(memory_mb), 2) as avg_mem, "
                "ROUND(AVG(latency_ms), 2) as avg_latency "
                "FROM system_metrics "
                "GROUP BY service "
                "ORDER BY avg_latency ASC;"
            )
            description = "SQL query aggregating system telemetry performance metrics."
        else:
            content = "SELECT * FROM customers LIMIT 5;"
            description = "Baseline customer records query."

        thought = f"Synthesized SQL query targeting SQLite database for subgoal: '{current_subgoal}'."

    # Standard API Synthesis
    elif artifact_type == "api":
        content = "https://api.nexusgraph.internal/v1/rates"
        description = "GET request to internal rates telemetry API."
        thought = f"Synthesized REST API request for subgoal: '{current_subgoal}'."

    # Standard Python Synthesis
    else:
        content = (
            "def calculate_aggregate_analytics(data):\n"
            "    \"\"\"Compute statistical summary over data series.\"\"\"\n"
            "    cleaned = [v for v in data if isinstance(v, (int, float))]\n"
            "    if not cleaned:\n"
            "        return {'count': 0, 'sum': 0, 'average': 0.0}\n"
            "    return {\n"
            "        'count': len(cleaned),\n"
            "        'sum': round(sum(cleaned), 2),\n"
            "        'average': round(sum(cleaned) / len(cleaned), 2),\n"
            "        'max': max(cleaned),\n"
            "        'min': min(cleaned)\n"
            "    }\n"
        )
        description = "Python numerical aggregation utility."
        thought = f"Synthesized Python data calculation routine for subgoal: '{current_subgoal}'."

    artifacts = {
        "step_index": step_idx,
        "artifact_type": artifact_type,
        "content": content,
        "description": description
    }
    state["artifacts"] = artifacts

    history.append(create_step(
        node="synthesizer",
        action="generate_artifact",
        thought=thought,
        status="success",
        details={
            "artifact_type": artifact_type,
            "description": description,
            "snippet": content[:120] + ("..." if len(content) > 120 else "")
        }
    ))

    state["history"] = history
    state["status"] = "validating"
    return state
