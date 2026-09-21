import asyncio
from typing import Any, Dict, List, Optional
from app.core.qdrant_client import get_vector_client


class RetrievalTool:
    """
    Semantic search tool querying the in-memory FAISS vector index.
    Zero-dependency replacement for external Qdrant in demo environments.
    """
    name: str = "retrieval_tool"
    description: str = "Perform semantic search across database schemas, tool definitions, and system specifications."

    def __init__(self):
        self.client = get_vector_client()

    def search_sync(self, query: str, top_k: int = 3, category: Optional[str] = None) -> Dict[str, Any]:
        results = self.client.search(query=query, top_k=top_k, category=category)
        return {
            "query": query,
            "count": len(results),
            "results": results,
            "source": "faiss_in_memory"
        }

    async def execute(self, query: str, top_k: int = 3, category: Optional[str] = None) -> Dict[str, Any]:
        return await asyncio.to_thread(self.search_sync, query, top_k, category)


retrieval_tool = RetrievalTool()
