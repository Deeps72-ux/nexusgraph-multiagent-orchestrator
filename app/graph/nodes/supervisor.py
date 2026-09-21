from typing import Any, Dict, Literal
from app.graph.state import GraphState, create_step


def supervisor_node(state: GraphState) -> GraphState:
    """
    Supervisor / Central Dispatcher:
    Monitors workflow state, tracks progress across plan steps,
    and decides the next sub-agent to invoke.
    """
    history = list(state.get("history", []))
    plan = state.get("plan", [])
    step_idx = state.get("current_step_index", 0)
    validation = state.get("validation_results", {})
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    artifacts = state.get("artifacts", {})
    tool_results = state.get("tool_results", {})
    healing_history = state.get("healing_history", [])

    # 1. No plan yet -> Send to Planner
    if not plan:
        thought = "No execution plan established yet. Routing to Planner agent for task decomposition."
        history.append(create_step(
            node="supervisor",
            action="route_to_planner",
            thought=thought,
            status="running",
            details={"destination": "planner"}
        ))
        state["history"] = history
        state["next_node"] = "planner"
        state["status"] = "planning"
        return state

    # 2. Plan finished -> Finalize and route to END
    if step_idx >= len(plan):
        thought = f"All {len(plan)} planned sub-goals successfully executed. Finalizing orchestration."
        history.append(create_step(
            node="supervisor",
            action="finalize_workflow",
            thought=thought,
            status="success",
            details={"completed_steps": len(plan)}
        ))
        state["history"] = history
        state["next_node"] = "end"
        state["status"] = "completed"

        # Build detailed final summary
        summary_lines = [
            f"### Multi-Agent Orchestration Completed Successfully",
            f"**Task**: {state.get('task')}",
            f"**Run ID**: `{state.get('run_id')}`",
            "",
            "#### Executed Plan Steps:",
        ]
        for i, step in enumerate(plan, 1):
            summary_lines.append(f"{i}. {step}")

        summary_lines.append("")
        if healing_history:
            summary_lines.append(f"#### Self-Healing Log:")
            summary_lines.append(f"- **Recoveries Made**: {len(healing_history)}")
            for h in healing_history:
                summary_lines.append(f"  - Attempt {h.get('attempt')}: {h.get('diagnosis')} -> Applied: `{h.get('fix_applied')}`")
            summary_lines.append("")

        if artifacts.get("content"):
            summary_lines.append(f"#### Validated Artifact ({artifacts.get('artifact_type', 'code').upper()}):")
            lang = "sql" if artifacts.get("artifact_type") == "sql" else "python"
            summary_lines.append(f"```{lang}\n{artifacts.get('content')}\n```")
            summary_lines.append("")

        if "database" in tool_results:
            db_res = tool_results["database"]
            summary_lines.append("#### Database Execution Results:")
            summary_lines.append(f"- **Rows Returned**: {db_res.get('row_count')}")
            summary_lines.append(f"- **Execution Time**: {db_res.get('execution_time_ms')}ms")
            if db_res.get("rows"):
                summary_lines.append(f"- **Sample Data**:")
                for r in db_res.get("rows")[:3]:
                    summary_lines.append(f"  - `{dict(r)}`")
            summary_lines.append("")

        if "api" in tool_results:
            api_res = tool_results["api"]
            summary_lines.append("#### API Execution Results:")
            summary_lines.append(f"- **Status Code**: {api_res.get('status_code')}")
            summary_lines.append(f"- **Endpoint**: `{api_res.get('url')}`")
            summary_lines.append(f"- **Payload**: `{api_res.get('data')}`")
            summary_lines.append("")

        state["final_output"] = "\n".join(summary_lines)
        return state

    # 3. Check if validation failed and we have retries remaining
    is_valid = validation.get("is_valid")
    if is_valid is False:
        if retry_count < max_retries:
            thought = f"Artifact validation failed. Invoking Self-Healing agent (Attempt {retry_count + 1}/{max_retries})."
            history.append(create_step(
                node="supervisor",
                action="route_to_healing",
                thought=thought,
                status="warning",
                details={"retry_count": retry_count, "errors": validation.get("errors", [])}
            ))
            state["history"] = history
            state["next_node"] = "healing"
            state["status"] = "healing"
            return state
        else:
            thought = f"Max retries ({max_retries}) exceeded during self-healing. Aborting with failure state."
            history.append(create_step(
                node="supervisor",
                action="abort_max_retries",
                thought=thought,
                status="error",
                details={"retry_count": retry_count}
            ))
            state["history"] = history
            state["next_node"] = "end"
            state["status"] = "failed"
            state["final_output"] = f"Workflow failed: Max healing retries ({max_retries}) reached without resolving errors: {validation.get('errors')}"
            return state

    # 4. Check if artifact needs to be synthesized
    if not artifacts or artifacts.get("step_index") != step_idx:
        current_subgoal = plan[step_idx]
        thought = f"Step {step_idx + 1}/{len(plan)}: Routing to Synthesizer for subgoal: '{current_subgoal}'."
        history.append(create_step(
            node="supervisor",
            action="route_to_synthesizer",
            thought=thought,
            status="running",
            details={"step_index": step_idx, "subgoal": current_subgoal}
        ))
        state["history"] = history
        state["current_subgoal"] = current_subgoal
        state["next_node"] = "synthesizer"
        state["status"] = "synthesizing"
        return state

    # 5. Artifact synthesized but not validated yet
    if "is_valid" not in validation:
        thought = f"Artifact for step {step_idx + 1} generated. Routing to Validator for AST/schema inspection."
        history.append(create_step(
            node="supervisor",
            action="route_to_validator",
            thought=thought,
            status="running",
            details={"artifact_type": artifacts.get("artifact_type")}
        ))
        state["history"] = history
        state["next_node"] = "validator"
        state["status"] = "validating"
        return state

    # 6. Artifact is valid -> Advance to next plan step
    if is_valid is True:
        thought = f"Step {step_idx + 1}/{len(plan)} validated successfully. Advancing workflow."
        history.append(create_step(
            node="supervisor",
            action="advance_step",
            thought=thought,
            status="success",
            details={"completed_step": step_idx}
        ))
        # Clear per-step validation/artifacts for subsequent steps
        new_step_idx = step_idx + 1
        state["current_step_index"] = new_step_idx
        state["validation_results"] = {}
        state["history"] = history
        if new_step_idx >= len(plan):
            state["next_node"] = "end"
            state["status"] = "completed"
            summary_lines = [
                f"### Multi-Agent Orchestration Completed Successfully",
                f"**Task**: {state.get('task')}",
                f"**Run ID**: `{state.get('run_id')}`",
                "",
                "#### Executed Plan Steps:",
            ]
            for i, step in enumerate(plan, 1):
                summary_lines.append(f"{i}. {step}")

            summary_lines.append("")
            if healing_history:
                summary_lines.append(f"#### Self-Healing Log:")
                summary_lines.append(f"- **Recoveries Made**: {len(healing_history)}")
                for h in healing_history:
                    summary_lines.append(f"  - Attempt {h.get('attempt')}: {h.get('diagnosis')} -> Applied: `{h.get('fix_applied')}`")
                summary_lines.append("")

            if artifacts.get("content"):
                summary_lines.append(f"#### Validated Artifact ({artifacts.get('artifact_type', 'code').upper()}):")
                lang = "sql" if artifacts.get("artifact_type") == "sql" else "python"
                summary_lines.append(f"```{lang}\n{artifacts.get('content')}\n```")
                summary_lines.append("")

            if "database" in tool_results:
                db_res = tool_results["database"]
                summary_lines.append("#### Database Execution Results:")
                summary_lines.append(f"- **Rows Returned**: {db_res.get('row_count')}")
                summary_lines.append(f"- **Execution Time**: {db_res.get('execution_time_ms')}ms")
                if db_res.get("rows"):
                    summary_lines.append(f"- **Sample Data**:")
                    for r in db_res.get("rows")[:3]:
                        summary_lines.append(f"  - `{dict(r)}`")
                summary_lines.append("")

            if "api" in tool_results:
                api_res = tool_results["api"]
                summary_lines.append("#### API Execution Results:")
                summary_lines.append(f"- **Status Code**: {api_res.get('status_code')}")
                summary_lines.append(f"- **Endpoint**: `{api_res.get('url')}`")
                summary_lines.append(f"- **Payload**: `{api_res.get('data')}`")
                summary_lines.append("")

            state["final_output"] = "\n".join(summary_lines)
        else:
            state["next_node"] = "synthesizer"
            state["status"] = "synthesizing"
            state["current_subgoal"] = plan[new_step_idx]
        return state

    # Fallback to end
    state["next_node"] = "end"
    return state


def route_supervisor(state: GraphState) -> Literal["planner", "synthesizer", "validator", "healing", "__end__"]:
    """Routing function for LangGraph conditional edge from supervisor."""
    next_node = state.get("next_node", "end")
    if next_node == "planner":
        return "planner"
    elif next_node == "synthesizer":
        return "synthesizer"
    elif next_node == "validator":
        return "validator"
    elif next_node == "healing":
        return "healing"
    return "__end__"
