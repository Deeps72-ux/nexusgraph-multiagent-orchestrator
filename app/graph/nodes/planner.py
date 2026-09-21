from typing import List
from app.graph.state import GraphState, create_step
from app.tools.retrieval_tool import retrieval_tool


def planner_node(state: GraphState) -> GraphState:
    """
    Planner Sub-Agent:
    Analyzes task requirements, retrieves domain context from FAISS,
    and decomposes complex objectives into sequential sub-goals.
    """
    task = state.get("task", "")
    history = list(state.get("history", []))

    # Retrieve relevant domain schemas / guidelines from FAISS index
    search_res = retrieval_tool.search_sync(query=task, top_k=2)
    retrieved_titles = [doc.get("title", "") for doc in search_res.get("results", [])]

    # Decompose into structured sub-goals based on task intent
    task_lower = task.lower()
    plan: List[str] = []

    if any(k in task_lower for k in ["sql", "database", "transaction", "customer", "spend", "revenue", "product", "metric", "table"]):
        plan = [
            "Retrieve database schema metadata and table relations",
            "Synthesize read-only SQL analytical query with aggregations",
            "Validate SQL safety rules and execute query against database",
            "Synthesize final analytical report and key business insights"
        ]
    elif any(k in task_lower for k in ["heal", "syntax", "error", "repair", "ast", "broken"]):
        plan = [
            "Analyze target code requirements and syntax constraints",
            "Synthesize implementation code (verifying self-healing resilience)",
            "Perform AST syntax validation and structural compliance checks",
            "Compile execution results and verification summary"
        ]
    elif any(k in task_lower for k in ["api", "http", "rates", "endpoint", "rest"]):
        plan = [
            "Retrieve REST API endpoint specifications and parameters",
            "Synthesize HTTP request payload and headers",
            "Validate request schema and dispatch HTTP query",
            "Synthesize structured response summary"
        ]
    else:
        plan = [
            "Retrieve relevant domain context and operational specifications",
            "Synthesize computational logic or query to satisfy task objective",
            "Perform AST and schema validation on generated artifact",
            "Format final results and deliver execution insights"
        ]

    state["plan"] = plan
    state["current_step_index"] = 0
    state["current_subgoal"] = plan[0]
    state["tool_results"] = state.get("tool_results", {})
    state["tool_results"]["retrieval"] = search_res

    thought = (
        f"Decomposed task into {len(plan)} sub-goals with {len(retrieved_titles)} contextual documents retrieved: "
        f"{', '.join(retrieved_titles)}."
    )

    history.append(create_step(
        node="planner",
        action="task_decomposition",
        thought=thought,
        status="success",
        details={
            "plan": plan,
            "retrieved_context": retrieved_titles,
            "subgoal_count": len(plan)
        }
    ))

    state["history"] = history
    state["status"] = "synthesizing"
    return state
