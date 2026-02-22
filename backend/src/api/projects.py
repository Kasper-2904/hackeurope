"""Project and Task routing endpoints."""

import asyncio
import json
from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.auth import get_current_user, require_pm_role_for_project
from src.api.schemas import (
    ProjectAllowedAgentResponse,
    ProjectCreate,
    ProjectResponse,
    TaskCreate,
    TaskDetail,
    TaskLogResponse,
    TaskLogsResponse,
    TaskProgress,
    TaskReasoningLogResponse,
    TaskResponse,
    TaskStartRequest,
    TaskStartResponse,
    TaskStatusUpdate,
)
from src.core.reasoning_logs import get_reasoning_stream_hub
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import PlanStatus, SubtaskStatus, TaskStatus
from src.storage.database import get_db
from src.storage.models import (
    Agent,
    MarketplaceAgent,
    Plan,
    Project,
    ProjectAllowedAgent,
    Subtask,
    Task,
    TaskLog,
    TaskReasoningLog,
    TeamMember,
    User,
)

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
    """List all projects visible to the authenticated user.

    Returns all workspace projects — any authenticated user can see
    every project in the workspace.
    """
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


@projects_router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Project:
    """Get a single project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return project


@projects_router.get("/{project_id}/tasks", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Task]:
    """List project tasks from both plan links and direct project-scoped creation."""
    from src.storage.models import Plan

    # Get task IDs from plans for this project
    task_ids_query = select(Plan.task_id).where(Plan.project_id == project_id)

    result = await db.execute(
        select(Task)
        .where((Task.id.in_(task_ids_query)) | (Task.team_id == project_id))
        .order_by(Task.created_at.desc())
    )
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
    """Add an agent to a project's allowlist.

    The agent can be:
    1. An agent owned by the current user, OR
    2. A marketplace agent (published and active)
    """
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # First try to find agent owned by user
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    )
    agent = agent_result.scalar_one_or_none()

    # If not owned by user, check if it's a marketplace agent (published)
    if not agent:
        marketplace_result = await db.execute(
            select(MarketplaceAgent).where(
                MarketplaceAgent.agent_id == agent_id,
                MarketplaceAgent.is_active == True,
            )
        )
        marketplace_agent = marketplace_result.scalar_one_or_none()

        if marketplace_agent:
            # Get the underlying agent
            agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = agent_result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found. Must be an agent you own or a published marketplace agent.",
        )

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


@projects_router.delete(
    "/{project_id}/allowlist/{agent_id}", status_code=status.HTTP_204_NO_CONTENT
)
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
    project_scope_id = task_data.project_id or task_data.team_id

    if task_data.project_id and task_data.team_id and task_data.project_id != task_data.team_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id and team_id must match when both are provided",
        )

    if project_scope_id:
        await require_pm_role_for_project(db, current_user, project_scope_id)

    task = Task(
        id=str(uuid4()),
        title=task_data.title,
        description=task_data.description,
        task_type=task_data.task_type,
        input_data=task_data.input_data,
        team_id=project_scope_id,
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
    """List tasks the user has access to (created by or is team member)."""
    from src.storage.models import TeamMember, Project

    # Get projects where user is a member or owner
    member_project_ids = select(TeamMember.project_id).where(TeamMember.user_id == current_user.id)

    # Also get projects owned by user
    owned_project_ids = select(Project.id).where(Project.owner_id == current_user.id)

    query = select(Task).where(
        (Task.created_by_id == current_user.id)
        | (Task.team_id.in_(member_project_ids))
        | (Task.team_id.in_(owned_project_ids))
    )

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
    return await _get_task_with_access(task_id=task_id, current_user=current_user, db=db)


async def _get_task_with_access(task_id: str, current_user: User, db: AsyncSession) -> Task:
    """Return task if visible to user, else raise 404."""
    from src.storage.models import TeamMember, Project

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Check access - user must be creator, owner of task's team, or team member
    if task.created_by_id != current_user.id:
        # Check if user is member of any project or owner
        member_result = await db.execute(
            select(TeamMember).where(TeamMember.user_id == current_user.id)
        )
        member = member_result.scalar_one_or_none()

        # Check if user owns the project
        if task.team_id:
            project_result = await db.execute(
                select(Project).where(
                    Project.id == task.team_id, Project.owner_id == current_user.id
                )
            )
            project = project_result.scalar_one_or_none()
            if not project and not member:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        elif not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return task


@tasks_router.get("/{task_id}/reasoning-logs", response_model=list[TaskReasoningLogResponse])
async def list_task_reasoning_logs(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TaskReasoningLog]:
    """Get persisted reasoning log timeline for a task."""
    await _get_task_with_access(task_id=task_id, current_user=current_user, db=db)

    result = await db.execute(
        select(TaskReasoningLog)
        .where(TaskReasoningLog.task_id == task_id)
        .order_by(
            TaskReasoningLog.sequence.asc(),
            TaskReasoningLog.created_at.asc(),
            TaskReasoningLog.id.asc(),
        )
    )
    return list(result.scalars().all())


@tasks_router.get("/{task_id}/reasoning-logs/stream")
async def stream_task_reasoning_logs(
    task_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """SSE stream for live reasoning log updates for a task."""
    await _get_task_with_access(task_id=task_id, current_user=current_user, db=db)
    stream_hub = get_reasoning_stream_hub()
    queue = await stream_hub.subscribe(task_id)

    async def event_stream():
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event_payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_name = event_payload.get("event", "reasoning_log.created")
                    data = json.dumps(event_payload, default=str)
                    yield f"event: {event_name}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            await stream_hub.unsubscribe(task_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@tasks_router.patch("/{task_id}", response_model=TaskResponse)
async def update_task_status(
    task_id: str,
    update_data: TaskStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Task:
    """
    Update task status. Valid transitions:
    - PENDING -> ASSIGNED (requires assigned_agent_id)
    - PENDING -> IN_PROGRESS
    - ASSIGNED -> IN_PROGRESS
    - IN_PROGRESS -> COMPLETED
    - IN_PROGRESS -> FAILED
    - Any -> CANCELLED
    """
    event_bus = get_event_bus()

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Define valid status transitions
    valid_transitions: dict[TaskStatus, list[TaskStatus]] = {
        TaskStatus.PENDING: [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
        TaskStatus.ASSIGNED: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
        TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.COMPLETED: [TaskStatus.CANCELLED],
        TaskStatus.FAILED: [TaskStatus.PENDING, TaskStatus.CANCELLED],
        TaskStatus.CANCELLED: [TaskStatus.PENDING],
    }

    current_status = task.status
    new_status = update_data.status

    if new_status not in valid_transitions.get(current_status, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from {current_status.value} to {new_status.value}",
        )

    # Handle specific transitions
    if new_status == TaskStatus.ASSIGNED:
        if not update_data.assigned_agent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="assigned_agent_id is required when setting status to ASSIGNED",
            )
        # Verify agent exists
        agent_result = await db.execute(
            select(Agent).where(Agent.id == update_data.assigned_agent_id)
        )
        if not agent_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        task.assigned_agent_id = update_data.assigned_agent_id
        task.assigned_at = datetime.utcnow()

    if new_status == TaskStatus.IN_PROGRESS:
        task.started_at = datetime.utcnow()

    if new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        task.completed_at = datetime.utcnow()
        if new_status == TaskStatus.COMPLETED:
            task.progress = 1.0

    task.status = new_status
    await db.commit()
    await db.refresh(task)

    # Publish status change event
    await event_bus.publish(
        Event(
            type=EventType.TASK_PROGRESS,
            data={
                "task_id": task.id,
                "old_status": current_status.value,
                "new_status": new_status.value,
            },
            source="api",
        )
    )

    return task


@tasks_router.patch("/{task_id}/progress", response_model=TaskResponse)
async def update_task_progress(
    task_id: str,
    progress_data: TaskProgress,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Task:
    """
    Update task progress (0.0 to 1.0).

    This is used by agents or the system to report progress on a task.
    If progress reaches 1.0, the task status is automatically set to COMPLETED.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status not in (TaskStatus.IN_PROGRESS, TaskStatus.ASSIGNED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update progress for task with status {task.status.value}",
        )

    task.progress = progress_data.progress

    # Auto-complete if progress reaches 100%
    if progress_data.progress >= 1.0:
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.progress = 1.0

    await db.commit()
    await db.refresh(task)

    # Publish progress event
    event_bus = get_event_bus()
    await event_bus.publish(
        Event(
            type=EventType.TASK_PROGRESS,
            data={
                "task_id": task.id,
                "progress": task.progress,
                "message": progress_data.message,
            },
            source="api",
        )
    )

    return task


async def _create_subtasks_from_plan(session: AsyncSession, task_id: str, plan_id: str) -> list:
    """Create subtasks from the approved plan."""
    from uuid import uuid4

    # Get the plan
    plan_result = await session.execute(select(Plan).where(Plan.id == plan_id))
    plan = plan_result.scalar_one_or_none()

    if not plan or not plan.plan_data:
        return []

    subtask_data = plan.plan_data.get("subtasks", [])
    if not subtask_data:
        return []

    created_subtasks = []
    for idx, st_data in enumerate(subtask_data):
        subtask = Subtask(
            id=str(uuid4()),
            task_id=task_id,
            plan_id=plan_id,
            title=st_data.get("title", f"Subtask {idx + 1}"),
            description=st_data.get("description", ""),
            priority=st_data.get("priority", idx + 1),
            status=SubtaskStatus.PENDING.value,
        )
        session.add(subtask)
        created_subtasks.append(subtask)

    await session.commit()
    return created_subtasks


async def _run_task_orchestration(
    task_id: str,
    task_type: str,
    description: str,
    input_data: dict[str, Any] | None,
    team_id: str | None,
    user_id: str,
    project_id: str,
):
    """Background task to run the orchestrator for a task."""
    from src.core.orchestrator import get_orchestrator
    from src.services.task_manager import get_task_manager
    from src.storage.database import AsyncSessionLocal

    task_manager = get_task_manager()

    try:
        # First, create subtasks from the approved plan
        async with AsyncSessionLocal() as session:
            # Get approved plan for this task
            plan_result = await session.execute(
                select(Plan).where(
                    Plan.task_id == task_id, Plan.status == PlanStatus.APPROVED.value
                )
            )
            plan = plan_result.scalar_one_or_none()

            if plan:
                # Check if subtasks already exist
                subtask_check = await session.execute(
                    select(Subtask).where(Subtask.task_id == task_id)
                )
                existing_subtasks = subtask_check.scalars().all()

                if not existing_subtasks:
                    # Create subtasks from plan
                    await _create_subtasks_from_plan(session, task_id, plan.id)
                    print(f"Created subtasks from plan {plan.id}")

        orchestrator = get_orchestrator()
        result = await orchestrator.execute_task(
            task_id=task_id,
            task_type=task_type,
            description=description,
            input_data=input_data,
            team_id=team_id,
            user_id=user_id,
            project_id=project_id,
        )

        # Check if cancelled before updating
        if task_manager.is_running(task_id):
            # Update task status based on orchestrator result
            async with AsyncSessionLocal() as session:
                task_result = await session.execute(select(Task).where(Task.id == task_id))
                task = task_result.scalar_one_or_none()
                if task:
                    orch_status = result.get("status", "")
                    steps = result.get("steps", [])
                    total_steps = len(steps)

                    # Calculate progress based on completed steps
                    if total_steps > 0:
                        completed_steps = sum(1 for s in steps if s.get("result"))
                        task.progress = completed_steps / total_steps

                    if orch_status == "failed":
                        task.status = TaskStatus.FAILED
                        task.error = result.get("error")
                    elif orch_status in ("completed", "completed_with_errors"):
                        task.status = TaskStatus.COMPLETED
                        task.progress = 1.0
                        task.result = result
                    task.completed_at = datetime.utcnow()
                    await session.commit()

    except asyncio.CancelledError:
        print(f"Task {task_id} was cancelled")
        raise
    except Exception as e:
        print(f"Error in background orchestration for task {task_id}: {e}")
        # Update task status to FAILED
        async with AsyncSessionLocal() as session:
            task_result = await session.execute(select(Task).where(Task.id == task_id))
            task = task_result.scalar_one_or_none()
            if task:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.utcnow()
                await session.commit()


@tasks_router.post("/{task_id}/start", response_model=TaskStartResponse)
async def start_task(
    task_id: str,
    request: TaskStartRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Start a task by assigning an agent from the project's allowlist.

    This endpoint:
    1. Validates the task can be started
    2. Selects an appropriate agent from the project's allowlist
    3. Assigns the agent to the task
    4. Sets task status to IN_PROGRESS with initial progress
    5. Triggers orchestrator execution in background
    6. Returns immediately (does NOT wait for task completion)

    The actual work execution happens asynchronously via background task.
    """
    from src.services.agent_assignment import assign_agent_to_task

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status not in (TaskStatus.PENDING, TaskStatus.ASSIGNED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task cannot be started from status {task.status.value}",
        )

    # Assign an agent to the task based on project allowlist
    assignment_result = await assign_agent_to_task(
        db=db,
        task=task,
        project_id=request.project_id,
    )

    if assignment_result.get("error"):
        return {
            "task_id": task.id,
            "status": task.status.value,
            "message": "Failed to assign agent",
            "orchestration_result": None,
            "error": assignment_result.get("error"),
        }

    # Update task status to IN_PROGRESS
    task.status = TaskStatus.IN_PROGRESS
    task.started_at = datetime.utcnow()
    task.progress = 0.1  # Initial progress - task has started
    await db.commit()
    await db.refresh(task)

    # Publish event for task started
    event_bus = get_event_bus()
    await event_bus.publish(
        Event(
            type=EventType.TASK_STARTED,
            data={
                "task_id": task.id,
                "assigned_agent_id": task.assigned_agent_id,
                "project_id": request.project_id,
            },
            source="api",
        )
    )

    # Trigger orchestrator execution using task manager
    from src.services.task_manager import get_task_manager

    task_manager = get_task_manager()
    asyncio.create_task(
        _run_task_orchestration(
            task_id=task.id,
            task_type=task.task_type,
            description=task.description or task.title,
            input_data=task.input_data,
            team_id=task.team_id,
            user_id=current_user.id,
            project_id=request.project_id,
        )
    )

    return {
        "task_id": task.id,
        "status": task.status.value,
        "message": f"Task started and assigned to agent",
        "orchestration_result": {
            "assigned_agent_id": task.assigned_agent_id,
            "status": "in_progress",
        },
        "error": None,
    }


@tasks_router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Task:
    """Cancel a running task."""
    from src.services.task_manager import get_task_manager

    task_manager = get_task_manager()

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status not in (TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task cannot be cancelled from status {task.status.value}",
        )

    # Cancel the background task if running
    cancelled = task_manager.cancel(task_id)
    if cancelled:
        print(f"Cancelled running task {task_id}")

    # Update task status to CANCELLED
    task.status = TaskStatus.CANCELLED
    task.error = "Cancelled by user"
    await db.commit()
    await db.refresh(task)

    return task


@tasks_router.post("/{task_id}/execute", response_model=TaskStartResponse)
async def execute_task(
    task_id: str,
    request: TaskStartRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Execute a task synchronously through the orchestrator.

    This is for immediate execution - it will wait for the task to complete.
    Use /start for async task initiation instead.
    """
    from src.core.orchestrator import get_orchestrator

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status not in (TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task cannot be executed from status {task.status.value}",
        )

    # Update task status to IN_PROGRESS if not already
    if task.status != TaskStatus.IN_PROGRESS:
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()
        await db.commit()

    # Execute task through orchestrator with project context
    orchestrator = get_orchestrator()
    try:
        orchestration_result = await orchestrator.execute_task(
            task_id=task.id,
            task_type=task.task_type,
            description=task.description or task.title,
            input_data=task.input_data,
            team_id=task.team_id,
            user_id=current_user.id,
            project_id=request.project_id,
        )

        # Refresh task to get updates made by orchestrator
        await db.refresh(task)

        # Update task based on result
        orch_status = orchestration_result.get("status", "")
        if orch_status == "completed" or orch_status == "completed_with_errors":
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.result = orchestration_result
            task.completed_at = datetime.utcnow()
        elif orch_status == "failed":
            task.status = TaskStatus.FAILED
            task.error = orchestration_result.get("error")
            task.completed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(task)

        return {
            "task_id": task.id,
            "status": task.status.value,
            "message": "Task execution completed",
            "orchestration_result": orchestration_result,
            "error": orchestration_result.get("error"),
        }

    except Exception as e:
        await db.refresh(task)
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.completed_at = datetime.utcnow()
        await db.commit()

        return {
            "task_id": task.id,
            "status": "failed",
            "message": "Task execution failed",
            "orchestration_result": None,
            "error": str(e),
        }


@tasks_router.get("/{task_id}/logs", response_model=TaskLogsResponse)
async def get_task_logs(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    after_sequence: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Get task activity logs for real-time streaming.

    Use `after_sequence` for polling - only returns logs after that sequence number.
    This enables efficient polling without re-fetching all logs.
    """
    # Verify task exists
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Get logs after the specified sequence
    query = (
        select(TaskLog)
        .where(TaskLog.task_id == task_id, TaskLog.sequence > after_sequence)
        .order_by(TaskLog.sequence.asc())
        .limit(limit + 1)  # Get one extra to check if there's more
    )
    result = await db.execute(query)
    logs = list(result.scalars().all())

    has_more = len(logs) > limit
    if has_more:
        logs = logs[:limit]

    last_sequence = logs[-1].sequence if logs else after_sequence

    return {
        "task_id": task_id,
        "logs": logs,
        "has_more": has_more,
        "last_sequence": last_sequence,
    }


async def create_task_log(
    db: AsyncSession,
    task_id: str,
    log_type: str,
    message: str,
    agent_id: str | None = None,
    agent_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> TaskLog:
    """Helper function to create a task log entry."""
    # Get the next sequence number for this task
    result = await db.execute(
        select(TaskLog.sequence)
        .where(TaskLog.task_id == task_id)
        .order_by(TaskLog.sequence.desc())
        .limit(1)
    )
    last_seq = result.scalar_one_or_none()
    next_seq = (last_seq or 0) + 1

    log = TaskLog(
        id=str(uuid4()),
        task_id=task_id,
        log_type=log_type,
        agent_id=agent_id,
        agent_name=agent_name,
        message=message,
        details=details,
        sequence=next_seq,
    )
    db.add(log)
    await db.flush()
    return log
