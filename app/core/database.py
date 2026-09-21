import sqlite3
import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.core.config import settings

# Extract path from sqlite:/// URI
def get_db_path() -> str:
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "")
    return "./nexusgraph.db"

DB_PATH = get_db_path()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite database tables and seed demo data."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create Runs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        task TEXT NOT NULL,
        status TEXT NOT NULL,
        final_output TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # Create Checkpoints table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS checkpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        node_name TEXT NOT NULL,
        step_index INTEGER NOT NULL,
        state_json TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(run_id)
    )
    """)

    # Create Demo tables for tool execution
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        plan TEXT NOT NULL,
        country TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL,
        category TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service TEXT NOT NULL,
        cpu_pct REAL NOT NULL,
        memory_mb REAL NOT NULL,
        latency_ms REAL NOT NULL,
        recorded_at TEXT NOT NULL
    )
    """)

    # Seed demo data if customers table is empty
    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] == 0:
        customers = [
            ("Alice Chen", "alice@hyperion.io", "Enterprise", "US", "2024-01-15"),
            ("Marcus Vance", "marcus@vancetech.com", "Pro", "UK", "2024-02-10"),
            ("Elena Rostova", "elena@nordicscale.de", "Enterprise", "DE", "2024-03-01"),
            ("Kenji Sato", "kenji@tokyocore.jp", "Starter", "JP", "2024-03-12"),
            ("Sophia Rodriguez", "sophia@solaria.es", "Pro", "ES", "2024-04-05"),
            ("Liam O'Connor", "liam@celticcloud.ie", "Starter", "IE", "2024-04-18"),
            ("Priya Sharma", "priya@indusdynamics.in", "Enterprise", "IN", "2024-05-02"),
            ("Gabriel Silva", "gabriel@paulistalabs.br", "Pro", "BR", "2024-05-20"),
        ]
        cursor.executemany(
            "INSERT INTO customers (name, email, plan, country, created_at) VALUES (?, ?, ?, ?, ?)",
            customers
        )

        transactions = [
            (1, 4500.0, "completed", "subscription", "2024-04-01 10:00:00"),
            (1, 1200.0, "completed", "add-on", "2024-04-15 14:20:00"),
            (2, 850.0, "completed", "subscription", "2024-04-02 09:30:00"),
            (2, 220.0, "failed", "add-on", "2024-04-10 11:15:00"),
            (3, 9800.0, "completed", "subscription", "2024-04-03 16:45:00"),
            (4, 99.0, "completed", "subscription", "2024-04-05 08:00:00"),
            (5, 750.0, "completed", "subscription", "2024-04-06 12:10:00"),
            (7, 12500.0, "completed", "subscription", "2024-04-07 15:30:00"),
            (7, 3400.0, "completed", "professional_services", "2024-04-20 18:00:00"),
            (8, 620.0, "completed", "subscription", "2024-04-08 13:40:00"),
        ]
        cursor.executemany(
            "INSERT INTO transactions (customer_id, amount, status, category, created_at) VALUES (?, ?, ?, ?, ?)",
            transactions
        )

        products = [
            ("Nexus Neural Core", "AI Engine", 1999.00, 45),
            ("GraphState Mesh", "Orchestration", 799.00, 120),
            ("Qdrant Vector Adapter", "Vector DB", 399.00, 250),
            ("Autonomous Sentinel", "Security", 1299.00, 30),
            ("AST Healing Sandbox", "Compiler", 499.00, 85),
        ]
        cursor.executemany(
            "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
            products
        )

        metrics = [
            ("fastapi-gateway", 12.4, 384.5, 4.2, "2024-04-20 12:00:00"),
            ("langgraph-worker-1", 45.8, 1024.0, 48.6, "2024-04-20 12:00:00"),
            ("faiss-vector-engine", 28.1, 512.2, 12.3, "2024-04-20 12:00:00"),
            ("sqlite-store", 8.5, 128.0, 1.8, "2024-04-20 12:00:00"),
        ]
        cursor.executemany(
            "INSERT INTO system_metrics (service, cpu_pct, memory_mb, latency_ms, recorded_at) VALUES (?, ?, ?, ?, ?)",
            metrics
        )

    conn.commit()
    conn.close()


def execute_read_sql_sync(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute read-only SQL query synchronously and return results as list of dicts."""
    query_stripped = query.strip().upper()
    # Safety verification: strictly read-only
    dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "REPLACE", "CREATE", "GRANT", "REVOKE"]
    for word in dangerous_keywords:
        # Check if word starts as statement or statement contains it as a mutating clause
        if query_stripped.startswith(word) or f" {word} " in f" {query_stripped} ":
            raise ValueError(f"Write operation '{word}' is not permitted. Only SELECT / read-only queries are allowed.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


async def execute_read_sql(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute read-only SQL query in thread pool."""
    return await asyncio.to_thread(execute_read_sql_sync, query, params)


def save_run_sync(run_id: str, task: str, status: str, final_output: Optional[str] = None, error: Optional[str] = None) -> None:
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO runs (run_id, task, status, final_output, error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            status=excluded.status,
            final_output=excluded.final_output,
            error=excluded.error,
            updated_at=excluded.updated_at
        """, (run_id, task, status, final_output, error, now, now))
        conn.commit()
    finally:
        conn.close()


async def save_run(run_id: str, task: str, status: str, final_output: Optional[str] = None, error: Optional[str] = None) -> None:
    await asyncio.to_thread(save_run_sync, run_id, task, status, final_output, error)


def save_checkpoint_sync(run_id: str, node_name: str, step_index: int, state: Dict[str, Any]) -> None:
    now = datetime.utcnow().isoformat()
    state_json = json.dumps(state, default=str)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO checkpoints (run_id, node_name, step_index, state_json, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """, (run_id, node_name, step_index, state_json, now))
        conn.commit()
    finally:
        conn.close()


async def save_checkpoint(run_id: str, node_name: str, step_index: int, state: Dict[str, Any]) -> None:
    await asyncio.to_thread(save_checkpoint_sync, run_id, node_name, step_index, state)


def get_run_sync(run_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


async def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    return await asyncio.to_thread(get_run_sync, run_id)


def get_checkpoints_sync(run_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM checkpoints WHERE run_id = ? ORDER BY id ASC", (run_id,))
        rows = cursor.fetchall()
        checkpoints = []
        for r in rows:
            d = dict(r)
            try:
                d["state"] = json.loads(d["state_json"])
            except Exception:
                d["state"] = {}
            checkpoints.append(d)
        return checkpoints
    finally:
        conn.close()


async def get_checkpoints(run_id: str) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(get_checkpoints_sync, run_id)


def get_all_runs_sync(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


async def get_all_runs(limit: int = 50) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(get_all_runs_sync, limit)
