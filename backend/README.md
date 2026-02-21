# Agent Orchestrator Platform

A multi-agent orchestration platform with MCP (Model Context Protocol) support for software development tasks.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLOUD PLATFORM                                     │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        API Gateway (FastAPI)                           │  │
│  │         /auth, /agents, /teams, /tasks                                │  │
│  └────────────────────────────────┬──────────────────────────────────────┘  │
│                                   │                                          │
│  ┌────────────────────────────────▼──────────────────────────────────────┐  │
│  │                      ORCHESTRATOR (LangGraph)                          │  │
│  │    Routes tasks to appropriate connected agents                        │  │
│  └────────────────────────────────┬──────────────────────────────────────┘  │
│                                   │                                          │
│  ┌────────────────────────────────▼──────────────────────────────────────┐  │
│  │                    MCP CLIENT MANAGER                                  │  │
│  │    Platform acts as MCP Host - connects to agent MCP servers           │  │
│  └────────────────────────────────┬──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    Streamable HTTP (MCP Protocol)
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│  LOCAL AGENT  │          │  LOCAL AGENT  │          │  LOCAL AGENT  │
│  (MCP Server) │          │  (MCP Server) │          │  (MCP Server) │
│  Role: Coder  │          │ Role: Reviewer│          │  Role: Tester │
└───────────────┘          └───────────────┘          └───────────────┘
   Developer A                Developer B                CI Server
```

## Features

- **Agent Registration**: Local agents (MCP servers) sign in and register with the platform
- **Agent Marketplace**: Discover and purchase third-party agents, or publish your own
- **Seat & Usage Billing**: Integrated with Stripe (seats) and Paid.ai (agent usage metering)
- **Task Orchestration**: Create tasks and the orchestrator delegates to appropriate agents
- **Team Management**: Organize agents into teams
- **MCP Integration**: Full MCP protocol support via Streamable HTTP transport
- **JWT Authentication**: Secure agent and user authentication

## Quick Start

### 1. Start the Platform

```bash
# Install dependencies
uv sync

# Run the platform
uv run python -m src.main
```

The platform will be available at `http://localhost:8000`

### 2. Register a User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dev@example.com",
    "username": "developer",
    "password": "securepassword123"
  }'
```

### 3. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "developer",
    "password": "securepassword123"
  }'
```

### 4. Start a Local Agent

```bash
# In a separate terminal, start the example coder agent
uv run python -m src.agents.example_coder_agent
```

### 5. Register the Agent with the Platform

```bash
curl -X POST http://localhost:8000/api/v1/agents/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "My Coder Agent",
    "role": "coder",
    "description": "Local coding agent",
    "mcp_endpoint": "http://localhost:8001/mcp"
  }'
```

### 6. Connect to the Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/connect \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 7. Create a Task

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "title": "Review auth module",
    "task_type": "code_review",
    "input_data": {
      "file_path": "src/auth.py"
    }
  }'
```

## Project Structure

```
hackeurope/
├── src/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration
│   ├── core/
│   │   ├── event_bus.py     # Async event system
│   │   ├── state.py         # State definitions
│   │   └── orchestrator.py  # LangGraph orchestrator
│   ├── api/
│   │   ├── auth.py          # JWT authentication
│   │   ├── routes.py        # API endpoints
│   │   └── schemas.py       # Pydantic schemas
│   ├── mcp_client/
│   │   ├── connection.py    # MCP client connection
│   │   └── manager.py       # Connection manager
│   ├── storage/
│   │   ├── database.py      # SQLite async setup
│   │   └── models.py        # SQLAlchemy models
│   └── agents/
│       ├── example_coder_agent.py    # Example coder agent
│       └── example_reviewer_agent.py # Example reviewer agent
└── tests/
```

## Creating Your Own Local Agent

Create an MCP server that exposes tools for your specific use case:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="My Custom Agent")

@mcp.tool()
def my_tool(input: str) -> str:
    """My custom tool."""
    return f"Processed: {input}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8001)
```

Then register it with the platform using the API.

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Technology Stack

- **FastAPI**: API framework
- **LangGraph**: Orchestration workflow
- **MCP SDK**: Model Context Protocol
- **Stripe**: Seat-based subscriptions and Connect seller payouts
- **Paid.ai**: Usage-based agent billing and cost traces
- **SQLite**: Database (async with aiosqlite)
- **LiteLLM**: Multi-provider LLM support
- **JWT**: Authentication
