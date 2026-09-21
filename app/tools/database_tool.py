import time
from typing import Any, Dict, List
from app.core.database import execute_read_sql


class DatabaseTool:
    """
    Read-only SQL query execution tool against the SQLite database.
    Replaces PostgreSQL for zero-dependency demo deployments while preserving SQL interface.
    """
    name: str = "database_tool"
    description: str = "Execute read-only SQL queries (SELECT) against the database and return tabular results."

    async def execute(self, sql: str) -> Dict[str, Any]:
        start_time = time.perf_counter()
        try:
            # Clean and sanitize query
            clean_sql = sql.strip().rstrip(";")
            if not clean_sql:
                return {
                    "success": False,
                    "error": "Empty SQL statement provided.",
                    "rows": [],
                    "row_count": 0,
                    "execution_time_ms": 0.0
                }

            rows = await execute_read_sql(clean_sql)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            columns = list(rows[0].keys()) if rows else []

            return {
                "success": True,
                "sql": clean_sql,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "execution_time_ms": duration_ms
            }
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "sql": sql,
                "error": str(e),
                "rows": [],
                "row_count": 0,
                "execution_time_ms": duration_ms
            }


database_tool = DatabaseTool()
