"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from src.api.agents import agents_router
from src.api.users import auth_router, users_router
from src.api.projects import projects_router, tasks_router
from src.api.plans import plans_router
from src.api.subtasks import subtasks_router
from src.api.teams import teams_router, team_members_router
from src.api.risks import risks_router, reviewer_router
from src.api.dashboards import dashboard_router
from src.api.github import github_router
from src.api.marketplace import marketplace_router
from src.api.billing import billing_router

from src.config import get_settings
from src.core.event_bus import get_event_bus
from src.storage.database import init_db

health_router = APIRouter(tags=["Health"])


@health_router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@health_router.get("/agents/status")
async def agents_status() -> dict[str, Any]:
    """Get status of all agents."""
    return {"status": "ok", "message": "Use /api/v1/agents to list agents"}


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
        Agent Marketplace Platform - Buy, sell, and use AI agents.
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
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(plans_router, prefix="/api/v1")
    app.include_router(subtasks_router, prefix="/api/v1")
    app.include_router(teams_router, prefix="/api/v1")
    app.include_router(team_members_router, prefix="/api/v1")
    app.include_router(risks_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(reviewer_router, prefix="/api/v1")
    app.include_router(github_router, prefix="/api/v1")
    app.include_router(marketplace_router, prefix="/api/v1")
    app.include_router(billing_router, prefix="/api/v1")

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
