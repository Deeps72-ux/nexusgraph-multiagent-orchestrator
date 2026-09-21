import re
import math
import faiss
import numpy as np
from typing import Any, Dict, List, Optional

DIMENSION = 128

def _embed_text(text: str, dim: int = DIMENSION) -> np.ndarray:
    """
    Lightweight deterministic n-gram & word frequency vectorizer.
    Produces a normalized 128-dimensional embedding vector without external model weights.
    """
    vec = np.zeros(dim, dtype=np.float32)
    tokens = re.findall(r'\b\w+\b', text.lower())
    for token in tokens:
        # Hash word into dimension buckets
        h = hash(token)
        idx = abs(h) % dim
        weight = 1.0 / (1.0 + math.log(1 + len(token)))
        vec[idx] += weight

        # Also hash 3-character sub-tokens for semantic partial matches
        for i in range(max(0, len(token) - 2)):
            sub = token[i:i+3]
            sub_idx = abs(hash(sub)) % dim
            vec[sub_idx] += 0.4

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


class FAISSVectorStore:
    """
    In-memory vector store backed by FAISS IndexFlatIP (cosine similarity).
    Replaces external Qdrant deployment for zero-dependency standalone demo.
    """
    def __init__(self, dim: int = DIMENSION):
        self.dim = dim
        self.index = faiss.IndexFlatIP(self.dim)
        self.documents: List[Dict[str, Any]] = []

    def add_document(self, doc_id: str, title: str, content: str, category: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        doc = {
            "id": doc_id,
            "title": title,
            "content": content,
            "category": category,
            "metadata": metadata or {}
        }
        vec = _embed_text(f"{title} {content} {category}")
        self.index.add(np.expand_dims(vec, axis=0))
        self.documents.append(doc)

    def search(self, query: str, top_k: int = 3, category: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
            return []

        query_vec = _embed_text(query)
        # Search more if category filter requested
        k_search = min(self.index.ntotal, max(top_k * 3, 10))
        scores, indices = self.index.search(np.expand_dims(query_vec, axis=0), k_search)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1 or idx >= len(self.documents):
                continue
            doc = self.documents[idx].copy()
            if category and doc.get("category") != category:
                continue
            doc["score"] = float(round(score, 4))
            results.append(doc)
            if len(results) >= top_k:
                break

        return results

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": "FAISS (IndexFlatIP)",
            "total_documents": self.index.ntotal,
            "dimension": self.dim,
            "categories": list(set(d["category"] for d in self.documents))
        }


# Global singleton vector store
_vector_store: Optional[FAISSVectorStore] = None

def get_vector_client() -> FAISSVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = FAISSVectorStore()
        _seed_knowledge_base(_vector_store)
    return _vector_store


def _seed_knowledge_base(store: FAISSVectorStore) -> None:
    """Seed in-memory FAISS vector index with schemas, tool definitions, and agent guides."""
    docs = [
        {
            "id": "schema_customers",
            "title": "Database Schema: customers Table",
            "category": "database_schema",
            "content": "Table 'customers' fields: id (int primary key), name (text), email (text unique), plan (text: Enterprise, Pro, Starter), country (text: US, UK, DE, JP, ES, IE, IN, BR), created_at (date). Represents registered accounts.",
            "metadata": {"table": "customers"}
        },
        {
            "id": "schema_transactions",
            "title": "Database Schema: transactions Table",
            "category": "database_schema",
            "content": "Table 'transactions' fields: id (int primary key), customer_id (int foreign key -> customers.id), amount (real), status (text: completed, failed), category (text: subscription, add-on, professional_services), created_at (datetime).",
            "metadata": {"table": "transactions"}
        },
        {
            "id": "schema_products",
            "title": "Database Schema: products Table",
            "category": "database_schema",
            "content": "Table 'products' fields: id (int primary key), name (text), category (text: AI Engine, Orchestration, Vector DB, Security, Compiler), price (real), stock (int).",
            "metadata": {"table": "products"}
        },
        {
            "id": "schema_metrics",
            "title": "Database Schema: system_metrics Table",
            "category": "database_schema",
            "content": "Table 'system_metrics' fields: id (int primary key), service (text: fastapi-gateway, langgraph-worker-1, faiss-vector-engine, sqlite-store), cpu_pct (real), memory_mb (real), latency_ms (real), recorded_at (datetime).",
            "metadata": {"table": "system_metrics"}
        },
        {
            "id": "tool_database",
            "title": "Tool Definition: Read-Only Database Query",
            "category": "tool_definition",
            "content": "Tool 'database_tool' accepts a SQL SELECT query and executes it safely against the SQLite database. Mutation keywords (INSERT, UPDATE, DELETE, DROP) are strictly forbidden and rejected.",
            "metadata": {"tool": "database_tool"}
        },
        {
            "id": "tool_retrieval",
            "title": "Tool Definition: In-Memory Semantic Retrieval",
            "category": "tool_definition",
            "content": "Tool 'retrieval_tool' queries the in-memory FAISS index to find schemas, API parameters, or code signatures matching a natural language prompt.",
            "metadata": {"tool": "retrieval_tool"}
        },
        {
            "id": "tool_api",
            "title": "Tool Definition: Async HTTP API Client",
            "category": "tool_definition",
            "content": "Tool 'api_tool' sends asynchronous HTTP GET/POST requests using httpx to query external services or simulated endpoints.",
            "metadata": {"tool": "api_tool"}
        },
        {
            "id": "validation_ast_guide",
            "title": "Validation Spec: AST Parsing & Syntax Verification",
            "category": "spec",
            "content": "Validator node runs python ast.parse() on generated code artifacts. Catches SyntaxError, invalid indentation, unclosed parentheses, and dangerous builtins before execution.",
            "metadata": {"validator": "ast"}
        },
    ]

    for d in docs:
        store.add_document(d["id"], d["title"], d["content"], d["category"], d.get("metadata"))
