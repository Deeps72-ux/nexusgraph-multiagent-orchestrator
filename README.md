# NexusGraph: Autonomous Multi-Agent Orchestration Engine

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Stateful_Agents-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-red.svg?logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**NexusGraph** is an enterprise-grade multi-agent orchestration platform built with **FastAPI**, **LangGraph**, and **Qdrant**. It coordinates autonomous specialized sub-agents (Planner, Code Synthesizer, Query Validator, and Execution Engine) through stateful cyclic execution graphs, dynamic tool selection, human-in-the-loop checkpoints, and self-healing error recovery workflows.

---

## Architecture Overview

```mermaid
flowchart TD
    User([User / API Client]) -->|Request| API[FastAPI Gateway /ws/agent-stream]
    API --> Supervisor[Supervisor / Routing Agent]
    
    subgraph Agentic Orchestration Cycle [LangGraph State Machine]
        Supervisor --> Planner[Planner Agent]
        Planner -->|Decomposed Steps| Synthesizer[Code & Query Synthesizer]
        Synthesizer --> Validator[AST & Schema Validator]
        
        Validator -->|Valid| Executor[Tool Execution Node]
        Validator -->|Validation Failure| Healing[Self-Healing Correction Node]
        Healing -->|Refined State| Synthesizer
        
        Executor -->|Runtime Error| Healing
        Executor -->|Success| Checkpoint{Checkpoint / Verification}
    end

    Executor <--> Qdrant[(Qdrant Vector DB)]
    Executor <--> Postgres[(PostgreSQL Store)]
    Checkpoint -->|Complete| Response[Streaming WebSocket Output]
```

---

## Key Features

- **Stateful Cyclic Execution**: Built on **LangGraph** state machines to support complex loops, backtracking, and multi-turn planning rather than rigid DAGs.
- **Self-Healing Error Correction**: Captures validation failures, syntax errors, and runtime API exceptions; automatically feeds tracebacks back into the correction node for self-directed repair.
- **Dynamic Tool Dispatch**: Sub-agents discover and invoke tools dynamically using Qdrant vector retrieval for semantic tool discovery.
- **Human-in-the-Loop Checkpoints**: Configurable approval gates for high-stakes actions (e.g. database writes, external transactions).
- **Duplex Real-Time Streaming**: Real-time agent state broadcasting over WebSockets and Server-Sent Events (SSE).
- **Asynchronous & Containerized**: Fully asynchronous FastAPI backend containerized with Docker and production docker-compose recipes.

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend & API** | Python 3.11, FastAPI, Uvicorn, AsyncIO, WebSockets |
| **Agent Orchestration** | LangGraph, LangChain Core, Pydantic v2 |
| **LLM Inference** | Groq (Llama 3.3 70B / Qwen), OpenAI GPT-4o / Claude 3.5 Sonnet |
| **Vector & Storage** | Qdrant (Semantic Tool Discovery & Context), PostgreSQL (State Persistence) |
| **DevOps & Tooling** | Docker, Docker Compose, Pytest, Ruff, Pre-commit |

---

## Project Structure

```text
nexusgraph-multiagent-orchestrator/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── agents.py        # Trigger & manage workflows
│   │   │   │   ├── websocket.py     # Duplex streaming status
│   │   │   │   └── tools.py         # Dynamic tool catalog
│   │   └── router.py
│   ├── core/
│   │   ├── config.py                # Pydantic Settings & Env vars
│   │   ├── database.py              # Async PostgreSQL engine
│   │   └── qdrant_client.py         # Vector search client
│   ├── graph/
│   │   ├── state.py                 # GraphState schema (Pydantic)
│   │   ├── nodes/
│   │   │   ├── supervisor.py        # Central dispatcher
│   │   │   ├── planner.py           # Task decomposition
│   │   │   ├── synthesizer.py       # Code & query synthesis
│   │   │   ├── validator.py         # AST & schema validation
│   │   │   └── healing.py           # Self-healing feedback loop
│   │   └── workflow.py              # Compiled LangGraph instance
│   ├── tools/
│   │   ├── database_tool.py
│   │   ├── api_tool.py
│   │   └── retrieval_tool.py
│   └── main.py                      # FastAPI Application entrypoint
├── tests/
│   ├── test_graph.py
│   └── test_healing.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Quickstart

### 1. Clone & Setup Environment

```bash
git clone https://github.com/Deeps72-ux/nexusgraph-multiagent-orchestrator.git
cd nexusgraph-multiagent-orchestrator

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file:

```env
GROQ_API_KEY=gsk_your_groq_key
OPENAI_API_KEY=sk_your_openai_key
QDRANT_URL=http://localhost:6333
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/nexusgraph
ENVIRONMENT=development
```

### 3. Run with Docker Compose

```bash
docker-compose up --build -d
```

Access the interactive API docs at `http://localhost:8000/docs`.

---

## API Endpoints

- `POST /api/v1/orchestrate`: Trigger multi-agent pipeline with a user task.
- `GET /api/v1/state/{run_id}`: Fetch state checkpoints and execution logs.
- `WS /ws/agent-stream/{run_id}`: Stream real-time node transitions and thinking steps.

---

## License

This project is licensed under the MIT License.
