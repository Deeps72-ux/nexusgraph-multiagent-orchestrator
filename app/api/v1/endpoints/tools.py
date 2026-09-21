from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tools.retrieval_tool import retrieval_tool
from app.tools.database_tool import database_tool
from app.tools.api_tool import api_tool

router = APIRouter()


class ToolExecuteRequest(BaseModel):
    tool_name: str = Field(..., description="Name of tool: database_tool, retrieval_tool, or api_tool")
    query: Optional[str] = Field(None, description="Query string for database or retrieval tool")
    url: Optional[str] = Field(None, description="URL for api_tool")
    method: str = Field("GET", description="HTTP method for api_tool")
    top_k: int = Field(3, description="Top-k for retrieval tool")


@router.get(
    "",
    summary="List registered sub-agent tools",
    description="Returns metadata, schemas, and operational boundaries of all tools available to sub-agents."
)
async def list_tools():
    return {
        "count": 3,
        "tools": [
            {
                "name": retrieval_tool.name,
                "description": retrieval_tool.description,
                "engine": "FAISS (IndexFlatIP in-memory vector index)",
                "capabilities": ["Semantic search", "Database schema lookup", "Tool documentation retrieval"]
            },
            {
                "name": database_tool.name,
                "description": database_tool.description,
                "engine": "SQLite Engine (read-only safety sandbox)",
                "capabilities": ["Read-only SQL execution", "Tabular aggregation", "Schema verification"]
            },
            {
                "name": api_tool.name,
                "description": api_tool.description,
                "engine": "HTTPX Async Client (with mock telemetry fallback)",
                "capabilities": ["REST queries", "JSON payload serialization", "Simulated cluster metrics"]
            }
        ]
    }


@router.post(
    "/execute",
    summary="Directly execute a registered tool",
    description="Invokes a specific tool for diagnostics or manual inspection."
)
async def execute_tool_directly(request: ToolExecuteRequest):
    name = request.tool_name.lower().strip()
    if name in ["database", "database_tool", "sql"]:
        if not request.query:
            raise HTTPException(status_code=400, detail="Field 'query' containing SQL is required for database_tool.")
        return await database_tool.execute(request.query)

    elif name in ["retrieval", "retrieval_tool", "faiss", "vector"]:
        if not request.query:
            raise HTTPException(status_code=400, detail="Field 'query' is required for retrieval_tool.")
        return await retrieval_tool.execute(request.query, top_k=request.top_k)

    elif name in ["api", "api_tool", "http"]:
        if not request.url:
            raise HTTPException(status_code=400, detail="Field 'url' is required for api_tool.")
        return await api_tool.execute(url=request.url, method=request.method)

    raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found.")
