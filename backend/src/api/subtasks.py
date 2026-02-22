"""Subtask routing endpoints."""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from src.api.auth import get_current_user
from src.api.schemas import (
    SubtaskCreate,
    SubtaskDetail,
    SubtaskFinalize,
    SubtaskResponse,
    SubtaskUpdate,
)
from src.core.state import SubtaskStatus, TaskStatus
from src.core.orchestrator import get_orchestrator
from src.storage.database import get_db
from src.storage.models import AuditLog, Subtask, User, Task

subtasks_router = APIRouter(prefix="/subtasks", tags=["Subtasks"])


@subtasks_router.get("", response_model=list[SubtaskResponse])
async def list_subtasks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    task_id: str | None = None,
) -> list[Subtask]:
    """List subtasks, optionally filtered by task_id."""
    query = select(Subtask)

    if task_id:
        query = query.where(Subtask.task_id == task_id)

    result = await db.execute(query.order_by(Subtask.priority.asc(), Subtask.created_at.desc()))
    return list(result.scalars().all())


@subtasks_router.post("", response_model=SubtaskResponse, status_code=status.HTTP_201_CREATED)
async def create_subtask(
    subtask_data: SubtaskCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Subtask:
    """Create a new subtask."""
    subtask = Subtask(
        id=str(uuid4()),
        task_id=subtask_data.task_id,
        plan_id=subtask_data.plan_id,
        title=subtask_data.title,
        description=subtask_data.description,
        priority=subtask_data.priority,
        assignee_id=subtask_data.assignee_id,
        assigned_agent_id=subtask_data.assigned_agent_id,
        status=SubtaskStatus.PENDING.value,
    )
    db.add(subtask)
    await db.commit()
    await db.refresh(subtask)
    return subtask


@subtasks_router.get("/{subtask_id}", response_model=SubtaskDetail)
async def get_subtask(
    subtask_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Subtask:
    """Get subtask details."""
    result = await db.execute(select(Subtask).where(Subtask.id == subtask_id))
    subtask = result.scalar_one_or_none()

    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found")

    return subtask


@subtasks_router.patch("/{subtask_id}", response_model=SubtaskResponse)
async def update_subtask(
    subtask_id: str,
    update_data: SubtaskUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Subtask:
    """Update a subtask."""
    result = await db.execute(select(Subtask).where(Subtask.id == subtask_id))
    subtask = result.scalar_one_or_none()

    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            if field == "status":
                setattr(subtask, field, value.value)
            else:
                setattr(subtask, field, value)

    await db.commit()
    await db.refresh(subtask)
    return subtask


@subtasks_router.post("/{subtask_id}/finalize", response_model=SubtaskResponse)
async def finalize_subtask(
    subtask_id: str,
    finalize_data: SubtaskFinalize,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Subtask:
    """Finalize a subtask with the final content."""
    result = await db.execute(select(Subtask).where(Subtask.id == subtask_id))
    subtask = result.scalar_one_or_none()

    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found")

    subtask.final_content = finalize_data.final_content
    subtask.finalized_at = datetime.utcnow()
    subtask.finalized_by_id = current_user.id
    subtask.status = SubtaskStatus.FINALIZED.value

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="subtask_finalized",
        resource_type="subtask",
        resource_id=subtask_id,
        details={"final_content": finalize_data.final_content},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(subtask)
    return subtask


async def _run_subtask_orchestration(
    subtask_id: str,
    task_id: str,
    title: str,
    description: str,
    current_user_id: str,
    project_id: str | None = None,
):
    """Background task to run the orchestrator for a specific subtask."""
    from src.storage.database import AsyncSessionLocal
    from sqlalchemy import select

    try:
        orchestrator = get_orchestrator()
        result = await orchestrator.execute_task(
            task_id=task_id,
            subtask_id=subtask_id,
            task_type="subtask_execution",
            description=f"{title}\n{description}",
            user_id=current_user_id,
            project_id=project_id,
        )

        # Update subtask status based on orchestrator result
        async with AsyncSessionLocal() as session:
            subtask_result = await session.execute(select(Subtask).where(Subtask.id == subtask_id))
            subtask = subtask_result.scalar_one_or_none()
            if subtask:
                orch_status = result.get("status", "")
                if orch_status == "failed":
                    subtask.status = SubtaskStatus.FAILED
                elif orch_status in ("completed", "completed_with_errors"):
                    subtask.status = SubtaskStatus.DRAFT_GENERATED
                    subtask.draft_content = result.get("final_result", "")
                    subtask.draft_generated_at = datetime.now(timezone.utc)
                await session.commit()

    except Exception as e:
        logger.error("Error in background orchestration for subtask %s: %s", subtask_id, e)
        # Update subtask status to FAILED
        async with AsyncSessionLocal() as session:
            subtask_result = await session.execute(select(Subtask).where(Subtask.id == subtask_id))
            subtask = subtask_result.scalar_one_or_none()
            if subtask:
                subtask.status = SubtaskStatus.FAILED
                await session.commit()


@subtasks_router.post("/{subtask_id}/dispatch", response_model=SubtaskResponse)
async def dispatch_subtask(
    subtask_id: str,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Subtask:
    """Dispatch a subtask to its assigned autonomous agent for drafting."""
    result = await db.execute(select(Subtask).where(Subtask.id == subtask_id))
    subtask = result.scalar_one_or_none()

    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found")

    if not subtask.assigned_agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subtask must have an assigned_agent_id before dispatching",
        )

    # Fetch parent task to pass to orchestrator
    task_result = await db.execute(select(Task).where(Task.id == subtask.task_id))
    parent_task = task_result.scalar_one_or_none()

    if not parent_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent task not found for subtask",
        )

    # Update status to indicate agent is working on it
    subtask.draft_agent_id = subtask.assigned_agent_id

    await db.commit()
    await db.refresh(subtask)

    # Dispatch to orchestrator in background
    background_tasks.add_task(
        _run_subtask_orchestration,
        subtask_id=subtask.id,
        task_id=parent_task.id,
        title=subtask.title,
        description=subtask.description or "",
        current_user_id=current_user.id,
        project_id=parent_task.project_id,
    )

    return subtask
