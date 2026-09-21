import os
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.core.database import init_db
from app.core.qdrant_client import get_vector_client
from app.api.v1.router import api_router
from app.api.v1.endpoints.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events: initialize SQLite database with demo tables
    and warm in-memory FAISS vector index.
    """
    init_db()
    get_vector_client()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Autonomous Multi-Agent Orchestration Engine with LangGraph, FAISS, and Self-Healing",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 routes
app.include_router(api_router, prefix=settings.API_V1_STR)

# Include WebSocket routes at root /ws
app.include_router(ws_router)


# Health check endpoint
@app.get("/health", tags=["Health & Telemetry"])
async def health_check():
    return {
        "status": "healthy",
        "service": "NexusGraph Multi-Agent Orchestrator",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "vector_engine": "FAISS (in-memory)",
        "database_engine": "SQLite",
        "timestamp": datetime.utcnow().isoformat()
    }


# Static files mount
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Serve demo landing page at root
@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "NexusGraph API online. Visit /docs for OpenAPI specs."})
