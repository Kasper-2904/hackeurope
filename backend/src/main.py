"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import (
    agents_router,
    auth_router,
    dashboard_router,
    health_router,
    plans_router,
    projects_router,
    tasks_router,
    teams_router,
    users_router,
)
from src.config import get_settings
from src.core.event_bus import get_event_bus
from src.mcp_client.manager import get_mcp_manager
from src.storage.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()

    # Initialize database
    await init_db()
    print(f"Database initialized: {settings.database_url}")

    # Start event bus
    event_bus = get_event_bus()
    await event_bus.start()
    print("Event bus started")

    yield

    # Shutdown
    print("Shutting down...")

    # Close all MCP connections
    mcp_manager = get_mcp_manager()
    await mcp_manager.close_all()
    print("MCP connections closed")

    # Stop event bus
    await event_bus.stop()
    print("Event bus stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
        Multi-agent orchestration platform with MCP support.

        ## Features

        - **Agent Registration**: Register local agents (MCP servers) with the platform
        - **Task Orchestration**: Create tasks and let the orchestrator delegate to agents
        - **Team Management**: Organize agents into teams
        - **MCP Integration**: Full MCP protocol support for tool calling and resource access

        ## Architecture

        This platform acts as an MCP Host that connects to multiple MCP Servers (agents).
        Local agents run their own MCP servers and register with this platform.
        The orchestrator can then delegate tasks to the appropriate agents.
        """,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(teams_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")

    # Add new routers
    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(plans_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
