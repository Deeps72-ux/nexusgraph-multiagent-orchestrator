import time
import httpx
from typing import Any, Dict, Optional


class APITool:
    """
    HTTP API tool allowing agents to invoke external or simulated REST endpoints.
    """
    name: str = "api_tool"
    description: str = "Make asynchronous HTTP GET/POST requests to external REST APIs or local mock endpoints."

    # Pre-defined mock endpoints for zero-network testing
    MOCK_ENDPOINTS = {
        "https://api.nexusgraph.internal/v1/rates": {
            "status": 200,
            "data": {
                "base": "USD",
                "rates": {"EUR": 0.92, "GBP": 0.79, "JPY": 154.2, "INR": 83.4, "CAD": 1.36},
                "updated_at": "2024-04-20T12:00:00Z"
            }
        },
        "https://api.nexusgraph.internal/v1/system/status": {
            "status": 200,
            "data": {
                "cluster": "nexus-prod-east",
                "nodes_online": 12,
                "active_agents": 4,
                "health": "nominal"
            }
        }
    }

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: float = 8.0
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        clean_url = url.strip()
        method_upper = method.upper()

        # Check if URL matches simulated internal endpoint
        if clean_url in self.MOCK_ENDPOINTS:
            mock = self.MOCK_ENDPOINTS[clean_url]
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": True,
                "url": clean_url,
                "method": method_upper,
                "status_code": mock["status"],
                "data": mock["data"],
                "is_mock": True,
                "execution_time_ms": duration_ms
            }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method_upper == "GET":
                    response = await client.get(clean_url, headers=headers)
                elif method_upper == "POST":
                    response = await client.post(clean_url, headers=headers, json=json_data)
                elif method_upper == "PUT":
                    response = await client.put(clean_url, headers=headers, json=json_data)
                else:
                    return {
                        "success": False,
                        "url": clean_url,
                        "error": f"Unsupported HTTP method: {method_upper}",
                        "execution_time_ms": round((time.perf_counter() - start_time) * 1000, 2)
                    }

                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

                try:
                    payload = response.json()
                except Exception:
                    payload = response.text[:2000]

                return {
                    "success": response.is_success,
                    "url": clean_url,
                    "method": method_upper,
                    "status_code": response.status_code,
                    "data": payload,
                    "is_mock": False,
                    "execution_time_ms": duration_ms
                }
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "url": clean_url,
                "method": method_upper,
                "error": str(e),
                "is_mock": False,
                "execution_time_ms": duration_ms
            }


api_tool = APITool()
