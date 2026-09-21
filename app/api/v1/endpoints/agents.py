import json
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.graph.workflow import execute_workflow_stream
from app.core.database import get_run, get_checkpoints, get_all_runs
from app.api.v1.endpoints.websocket import manager

router = APIRouter()


class OrchestrateRequest(BaseModel):
    task: str = Field(..., description="Task description to orchestrate across sub-agents", min_length=3)
    run_id: Optional[str] = Field(None, description="Optional custom run ID")
    max_retries: int = Field(3, description="Maximum self-healing retries permitted", ge=1, le=10)
    stream: bool = Field(True, description="Whether to stream execution events via SSE")


class OrchestrateResponse(BaseModel):
    run_id: str
    task: str
    status: str
    final_output: Optional[str] = None
    healing_attempts: int = 0
    total_steps: int = 0


@router.post(
    "/orchestrate",
    summary="Trigger multi-agent orchestration pipeline",
    description="Accepts a task description, initiates the LangGraph state machine, and streams real-time execution trace."
)
async def orchestrate_task(request: OrchestrateRequest):
    run_id = request.run_id or f"run_{uuid.uuid4().hex[:10]}"

    async def sse_event_generator():
        async def on_ws_event(event_dict: Dict[str, Any]):
            await manager.broadcast_to_run(run_id, event_dict)

        async for event in execute_workflow_stream(
            task=request.task,
            run_id=run_id,
            max_retries=request.max_retries,
            on_event=on_ws_event
        ):
            json_str = json.dumps(event, default=str)
            yield f"data: {json_str}\n\n"

    if request.stream:
        return StreamingResponse(
            sse_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Run-ID": run_id,
                "Content-Type": "text/event-stream"
            }
        )
    else:
        # Non-streaming collector
        last_event: Dict[str, Any] = {}
        async for event in execute_workflow_stream(
            task=request.task,
            run_id=run_id,
            max_retries=request.max_retries
        ):
            last_event = event

        run_record = await get_run(run_id)
        return OrchestrateResponse(
            run_id=run_id,
            task=request.task,
            status=run_record.get("status", "unknown") if run_record else "unknown",
            final_output=run_record.get("final_output") if run_record else None,
            healing_attempts=len(last_event.get("healing_history", [])),
            total_steps=last_event.get("total_steps", 0)
        )


@router.get(
    "/state/{run_id}",
    summary="Fetch execution state and checkpoints",
    description="Returns detailed execution log, intermediate states, and checkpoints for a given run."
)
async def get_run_state(run_id: str):
    run_data = await get_run(run_id)
    if not run_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' was not found in state store."
        )

    checkpoints = await get_checkpoints(run_id)

    return {
        "run_id": run_id,
        "run": run_data,
        "checkpoints": checkpoints,
        "total_checkpoints": len(checkpoints)
    }


@router.get(
    "/runs",
    summary="List past execution runs",
    description="Returns list of historical pipeline executions and their terminal statuses."
)
async def list_runs(limit: int = Query(50, ge=1, le=100)):
    runs = await get_all_runs(limit=limit)
    return {
        "count": len(runs),
        "runs": runs
    }
