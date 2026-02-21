"""API routes for GitHub ingestion."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from src.api.auth import get_current_user
from src.api.schemas_github import GitHubContextResponse, GitHubSyncResponse
from src.config import get_settings
from src.core.event_bus import Event, EventType, get_event_bus
from src.services.github_service import GitHubService, HttpxGitHubProvider
from src.storage.database import get_db
from src.storage.models import Project, User

github_router = APIRouter(prefix="/projects", tags=["GitHub"])

_github_service: GitHubService | None = None


def get_github_service() -> GitHubService:
    global _github_service
    if _github_service is None:
        settings = get_settings()
        provider = None
        if settings.github_token:
            provider = HttpxGitHubProvider(
                token=settings.github_token,
                api_base_url=settings.github_api_base_url,
            )
        _github_service = GitHubService(provider=provider)
    return _github_service


@github_router.post(
    "/{project_id}/sync-github",
    response_model=GitHubSyncResponse,
)
async def sync_github(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Trigger a GitHub sync for a project. Fetches PRs, commits, CI status and creates risk signals."""
    event_bus = get_event_bus()
    service = get_github_service()

    # Verify project belongs to current user
    proj_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    await event_bus.publish(
        Event(
            type=EventType.GITHUB_SYNC_STARTED,
            data={"project_id": project_id},
            source="api",
        )
    )

    try:
        result = await service.sync_project(project_id, db)

        await event_bus.publish(
            Event(
                type=EventType.GITHUB_SYNC_COMPLETED,
                data={"project_id": project_id, **result},
                source="api",
            )
        )
        return result

    except ValueError as e:
        await event_bus.publish(
            Event(
                type=EventType.GITHUB_SYNC_FAILED,
                data={"project_id": project_id, "error": str(e)},
                source="api",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@github_router.get(
    "/{project_id}/github-context",
    response_model=GitHubContextResponse,
)
async def get_github_context(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get the cached GitHub context for a project."""
    # Verify project belongs to current user
    proj_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    service = get_github_service()
    ctx = await service.get_context(project_id, db)

    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No GitHub context found. Run POST /sync-github first.",
        )

    return ctx
