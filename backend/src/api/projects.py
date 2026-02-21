"""Project and Task routing endpoints."""

from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import get_current_user
from src.api.schemas import (
    ProjectAllowedAgentResponse,
    ProjectCreate,
    ProjectResponse,
    TaskCreate,
    TaskDetail,
    TaskResponse,
)
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import TaskStatus
from src.storage.database import get_db
from src.storage.models import Agent, Project, ProjectAllowedAgent, Task, User

projects_router = APIRouter(prefix="/projects", tags=["Projects"])
tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])

# ============== Project Routes ==============


@projects_router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Project:
    """Create a new project."""
    project = Project(
        id=str(uuid4()),
        name=project_data.name,
        description=project_data.description,
        goals=project_data.goals,
        milestones=project_data.milestones,
        timeline=project_data.timeline,
        github_repo=project_data.github_repo,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@projects_router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Project]:
    """List projects available in the current workspace."""
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


@projects_router.get(
    "/{project_id}/allowlist",
    response_model=list[ProjectAllowedAgentResponse],
)
async def list_project_allowed_agents(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectAllowedAgent]:
    """List project-level allowed agents for PM management."""
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await db.execute(
        select(ProjectAllowedAgent)
        .options(selectinload(ProjectAllowedAgent.agent))
        .where(ProjectAllowedAgent.project_id == project_id)
        .order_by(ProjectAllowedAgent.created_at.desc())
    )
    return list(result.scalars().all())


@projects_router.post(
    "/{project_id}/allowlist/{agent_id}",
    response_model=ProjectAllowedAgentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_allowed_agent(
    project_id: str,
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectAllowedAgent:
    """Add an agent to a project's allowlist."""
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    existing_result = await db.execute(
        select(ProjectAllowedAgent).where(
            ProjectAllowedAgent.project_id == project_id,
            ProjectAllowedAgent.agent_id == agent_id,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent is already allowed for this project",
        )

    allowed_agent = ProjectAllowedAgent(
        id=str(uuid4()),
        project_id=project_id,
        agent_id=agent_id,
        added_by_id=current_user.id,
    )
    db.add(allowed_agent)
    await db.commit()

    result = await db.execute(
        select(ProjectAllowedAgent)
        .options(selectinload(ProjectAllowedAgent.agent))
        .where(ProjectAllowedAgent.id == allowed_agent.id)
    )
    return result.scalar_one()


@projects_router.delete("/{project_id}/allowlist/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_allowed_agent(
    project_id: str,
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove an agent from a project's allowlist."""
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await db.execute(
        select(ProjectAllowedAgent).where(
            ProjectAllowedAgent.project_id == project_id,
            ProjectAllowedAgent.agent_id == agent_id,
        )
    )
    allowed_agent = result.scalar_one_or_none()
    if not allowed_agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allowed agent not found")

    await db.delete(allowed_agent)
    await db.commit()


# ============== Task Routes ==============


@tasks_router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Task:
    """
    Create a new task.

    If assigned_agent_id is provided, the task will be assigned to that agent.
    Otherwise, the orchestrator will choose an appropriate agent.
    """
    event_bus = get_event_bus()

    task = Task(
        id=str(uuid4()),
        title=task_data.title,
        description=task_data.description,
        task_type=task_data.task_type,
        input_data=task_data.input_data,
        team_id=task_data.team_id,
        assigned_agent_id=task_data.assigned_agent_id,
        created_by_id=current_user.id,
        status=TaskStatus.PENDING,
        extra_data=task_data.metadata,
    )

    if task_data.assigned_agent_id:
        task.status = TaskStatus.ASSIGNED
        task.assigned_at = datetime.utcnow()

    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Publish task created event
    await event_bus.publish(
        Event(
            type=EventType.TASK_CREATED,
            data={
                "task_id": task.id,
                "task_type": task.task_type,
                "assigned_agent_id": task.assigned_agent_id,
            },
            source="api",
        )
    )

    return task


@tasks_router.get("", response_model=list[TaskResponse])
async def list_tasks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    team_id: str | None = None,
    status: TaskStatus | None = None,
) -> list[Task]:
    """List tasks, optionally filtered by team and status."""
    query = select(Task).where(Task.created_by_id == current_user.id)

    if team_id:
        query = query.where(Task.team_id == team_id)
    if status:
        query = query.where(Task.status == status)

    result = await db.execute(query)
    return list(result.scalars().all())


@tasks_router.get("/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Task:
    """Get task details including input/output."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by_id == current_user.id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return task
