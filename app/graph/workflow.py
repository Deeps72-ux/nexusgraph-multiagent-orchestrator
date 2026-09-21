import uuid
import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, Optional
from langgraph.graph import StateGraph, START, END

from app.graph.state import GraphState
from app.graph.nodes.supervisor import supervisor_node, route_supervisor
from app.graph.nodes.planner import planner_node
from app.graph.nodes.synthesizer import synthesizer_node
from app.graph.nodes.validator import validator_node
from app.graph.nodes.healing import healing_node
from app.graph.nodes.executor import executor_node
from app.core.database import save_run, save_checkpoint


def route_validator_edge(state: GraphState) -> str:
    """Route from validator: to executor if valid, to healing if invalid."""
    val = state.get("validation_results", {})
    if val.get("is_valid") is True:
        return "executor"
    return "healing"


def route_executor_edge(state: GraphState) -> str:
    """Route from executor: to healing if runtime error occurred, else back to supervisor."""
    val = state.get("validation_results", {})
    if val.get("is_valid") is False:
        return "healing"
    return "supervisor"


def route_healing_edge(state: GraphState) -> str:
    """Route from healing: back to synthesizer if within max retries, else to supervisor."""
    if state.get("retry_count", 0) <= state.get("max_retries", 3):
        return "synthesizer"
    return "supervisor"


def create_nexus_graph() -> Any:
    """
    Constructs and compiles the NexusGraph multi-agent orchestration state machine.
    """
    builder = StateGraph(GraphState)

    # Register sub-agent nodes
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("planner", planner_node)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("validator", validator_node)
    builder.add_node("executor", executor_node)
    builder.add_node("healing", healing_node)

    # Entry point
    builder.add_edge(START, "supervisor")

    # Supervisor conditional routing
    builder.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "planner": "planner",
            "synthesizer": "synthesizer",
            "validator": "validator",
            "healing": "healing",
            "__end__": END
        }
    )

    # Planner routes back to supervisor
    builder.add_edge("planner", "supervisor")

    # Synthesizer directly advances to validator
    builder.add_edge("synthesizer", "validator")

    # Validator conditional branch: Valid -> Executor | Invalid -> Healing
    builder.add_conditional_edges(
        "validator",
        route_validator_edge,
        {
            "executor": "executor",
            "healing": "healing"
        }
    )

    # Executor conditional branch: Success -> Supervisor | Runtime Error -> Healing
    builder.add_conditional_edges(
        "executor",
        route_executor_edge,
        {
            "supervisor": "supervisor",
            "healing": "healing"
        }
    )

    # Healing conditional branch: Retry -> Synthesizer | Max Retries -> Supervisor
    builder.add_conditional_edges(
        "healing",
        route_healing_edge,
        {
            "synthesizer": "synthesizer",
            "supervisor": "supervisor"
        }
    )

    return builder.compile()


# Compiled singleton graph
nexus_graph = create_nexus_graph()


async def execute_workflow_stream(
    task: str,
    run_id: Optional[str] = None,
    max_retries: int = 3,
    on_event: Optional[Callable[[Dict[str, Any]], Any]] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Asynchronously executes the NexusGraph pipeline, yielding real-time transition events
    and saving state checkpoints to SQLite.
    """
    if not run_id:
        run_id = f"run_{uuid.uuid4().hex[:10]}"

    initial_state: GraphState = {
        "task": task,
        "run_id": run_id,
        "plan": [],
        "current_step_index": 0,
        "current_subgoal": None,
        "artifacts": {},
        "tool_results": {},
        "validation_results": {},
        "error_trace": None,
        "healing_history": [],
        "retry_count": 0,
        "max_retries": max_retries,
        "final_output": None,
        "status": "initialized",
        "history": [],
        "next_node": "planner"
    }

    # Record initial run in database
    await save_run(run_id, task, "running")

    # Yield initial creation event
    init_event = {
        "event": "run_started",
        "run_id": run_id,
        "task": task,
        "timestamp": datetime.utcnow().isoformat()
    }
    if on_event:
        try:
            await on_event(init_event)
        except Exception:
            pass
    yield init_event

    step_counter = 0
    final_state: GraphState = initial_state

    try:
        async for output in nexus_graph.astream(initial_state, stream_mode="updates"):
            for node_name, node_state in output.items():
                step_counter += 1
                final_state.update(node_state)

                # Extract latest step if available
                history = final_state.get("history", [])
                latest_step = history[-1] if history else {}

                # Save checkpoint in DB
                await save_checkpoint(run_id, node_name, step_counter, final_state)

                event_payload = {
                    "event": "node_transition",
                    "run_id": run_id,
                    "step": step_counter,
                    "node": node_name,
                    "status": final_state.get("status", "running"),
                    "current_step_index": final_state.get("current_step_index", 0),
                    "current_subgoal": final_state.get("current_subgoal"),
                    "thought": latest_step.get("thought", ""),
                    "action": latest_step.get("action", ""),
                    "artifacts": final_state.get("artifacts", {}),
                    "validation_results": final_state.get("validation_results", {}),
                    "retry_count": final_state.get("retry_count", 0),
                    "healing_history": final_state.get("healing_history", []),
                    "timestamp": datetime.utcnow().isoformat()
                }

                if on_event:
                    try:
                        await on_event(event_payload)
                    except Exception:
                        pass

                yield event_payload

        # Run complete
        status = final_state.get("status", "completed")
        final_output = final_state.get("final_output", "Task completed.")
        await save_run(run_id, task, status, final_output=final_output)

        complete_event = {
            "event": "run_completed",
            "run_id": run_id,
            "status": status,
            "final_output": final_output,
            "tool_results": final_state.get("tool_results", {}),
            "healing_history": final_state.get("healing_history", []),
            "total_steps": step_counter,
            "timestamp": datetime.utcnow().isoformat()
        }

        if on_event:
            try:
                await on_event(complete_event)
            except Exception:
                pass

        yield complete_event

    except Exception as e:
        error_msg = str(e)
        await save_run(run_id, task, "failed", error=error_msg)
        error_event = {
            "event": "run_failed",
            "run_id": run_id,
            "error": error_msg,
            "timestamp": datetime.utcnow().isoformat()
        }
        if on_event:
            try:
                await on_event(error_event)
            except Exception:
                pass
        yield error_event
