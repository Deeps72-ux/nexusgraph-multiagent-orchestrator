import ast
import re
import traceback
from typing import Any, Dict, List
from app.graph.state import GraphState, create_step
from app.core.database import get_connection


def validate_python_code(code: str) -> Dict[str, Any]:
    """
    Validates Python code using AST parsing and security safety checks.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as se:
        error_msg = f"SyntaxError at line {se.lineno}, column {se.offset}: {se.msg}"
        if se.text:
            error_msg += f"\n  Code: {se.text.strip()}"
        return {
            "is_valid": False,
            "errors": [error_msg],
            "details": {
                "lineno": se.lineno,
                "offset": se.offset,
                "msg": se.msg,
                "failed_line": se.text.strip() if se.text else None
            }
        }
    except Exception as e:
        return {
            "is_valid": False,
            "errors": [f"AST parse failure: {str(e)}"],
            "details": {"traceback": traceback.format_exc()}
        }

    # Security check: disallow dangerous builtins / modules
    forbidden_imports = {"os", "subprocess", "pty", "sys", "shutil"}
    forbidden_calls = {"eval", "exec", "__import__"}
    errors = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_imports:
                    errors.append(f"Security policy violation: Forbidden import '{alias.name}'.")
        elif isinstance(node, ast.ImportFrom):
            if node.module in forbidden_imports:
                errors.append(f"Security policy violation: Forbidden import from '{node.module}'.")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                errors.append(f"Security policy violation: Forbidden call '{node.func.id}()'.")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "details": {
            "node_count": len(list(ast.walk(tree))),
            "has_functions": any(isinstance(n, ast.FunctionDef) for n in ast.walk(tree)),
            "syntax_valid": True
        }
    }


def validate_sql_query(sql: str) -> Dict[str, Any]:
    """
    Validates SQL query: read-only safety, syntax, and schema table checks.
    """
    clean_sql = sql.strip().rstrip(";")
    sql_upper = clean_sql.upper()

    # 1. Read-only safety check
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "REPLACE", "CREATE", "GRANT", "REVOKE"]
    for word in forbidden:
        if clean_sql.upper().startswith(word) or f" {word} " in f" {sql_upper} ":
            return {
                "is_valid": False,
                "errors": [f"SQL safety violation: Write operation '{word}' is strictly prohibited. Only SELECT queries allowed."],
                "details": {"violating_keyword": word}
            }

    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
        return {
            "is_valid": False,
            "errors": ["SQL statement must start with SELECT or WITH."],
            "details": {"received_start": sql.split()[0] if sql.split() else "EMPTY"}
        }

    # 2. SQLite syntax and schema check via EXPLAIN
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"EXPLAIN {clean_sql}")
        cursor.fetchall()
    except Exception as e:
        return {
            "is_valid": False,
            "errors": [f"SQL execution / schema error: {str(e)}"],
            "details": {"sqlite_error": str(e)}
        }
    finally:
        conn.close()

    # 3. Known table verification
    known_tables = {"customers", "transactions", "products", "system_metrics"}
    found_tables = set(re.findall(r'\b(?:FROM|JOIN)\s+([a-zA-Z_0-9]+)\b', clean_sql, re.IGNORECASE))
    unknown_tables = found_tables - known_tables
    if unknown_tables:
        return {
            "is_valid": False,
            "errors": [f"Unknown table(s) referenced: {', '.join(unknown_tables)}. Known tables: {', '.join(known_tables)}."],
            "details": {"unknown_tables": list(unknown_tables), "known_tables": list(known_tables)}
        }

    return {
        "is_valid": True,
        "errors": [],
        "details": {
            "read_only": True,
            "tables_referenced": list(found_tables),
            "explain_plan_verified": True
        }
    }


def validate_api_request(url: str) -> Dict[str, Any]:
    """
    Validates API endpoint format and scheme.
    """
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        return {
            "is_valid": False,
            "errors": [f"Invalid API URL scheme: '{clean_url}'. URL must begin with http:// or https://."],
            "details": {"url": clean_url}
        }

    return {
        "is_valid": True,
        "errors": [],
        "details": {"url": clean_url, "scheme_valid": True}
    }


def validator_node(state: GraphState) -> GraphState:
    """
    Validator Sub-Agent:
    Performs deterministic syntax and schema verification on generated artifacts:
    - Python: AST parsing, syntax tree validation, security screening
    - SQL: Read-only enforcement, SQLite EXPLAIN check, table schema matching
    - API: URL scheme and structure verification
    """
    artifacts = state.get("artifacts", {})
    artifact_type = artifacts.get("artifact_type", "python")
    content = artifacts.get("content", "")
    history = list(state.get("history", []))

    if artifact_type == "python":
        res = validate_python_code(content)
    elif artifact_type == "sql":
        res = validate_sql_query(content)
    elif artifact_type == "api":
        res = validate_api_request(content)
    else:
        res = {"is_valid": True, "errors": [], "details": {}}

    state["validation_results"] = res

    if res["is_valid"]:
        thought = f"AST & schema validation passed for {artifact_type} artifact. No syntax defects or policy violations."
        status = "success"
        state["error_trace"] = None
        state["status"] = "validated"
    else:
        errors_joined = " | ".join(res["errors"])
        thought = f"Validation FAILED for {artifact_type} artifact: {errors_joined}"
        status = "error"
        state["error_trace"] = errors_joined
        state["status"] = "healing"

    history.append(create_step(
        node="validator",
        action="validate_artifact",
        thought=thought,
        status=status,
        details={
            "is_valid": res["is_valid"],
            "artifact_type": artifact_type,
            "errors": res.get("errors", []),
            "validation_details": res.get("details", {})
        }
    ))

    state["history"] = history
    return state
