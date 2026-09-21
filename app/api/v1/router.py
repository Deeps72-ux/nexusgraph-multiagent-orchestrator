from fastapi import APIRouter
from app.api.v1.endpoints import agents, websocket, tools

api_router = APIRouter()

api_router.include_router(agents.router, tags=["Agents & Orchestration"])
api_router.include_router(tools.router, prefix="/tools", tags=["Tool Catalog"])
