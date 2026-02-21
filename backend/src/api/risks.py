"""Risk routing endpoints."""

from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.schemas import (
    ReviewerFinalizeRequest,
    ReviewerFinalizeResponse,
    RiskSignalCreate,
    RiskSignalResolve,
    RiskSignalResponse,
)
from src.services.paid_service import get_paid_service
from src.storage.database import get_db
from src.storage.models import AuditLog, Project, RiskSignal, Task, User

risks_router = APIRouter(prefix="/risks", tags=["Risk Signals"])
reviewer_router = APIRouter(prefix="/reviewer", tags=["Reviewer Agent"])

# ============== Risk Signal Routes ==============


@risks_router.post("", response_model=RiskSignalResponse, status_code=status.HTTP_201_CREATED)
async def create_risk_signal(
    risk_data: RiskSignalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RiskSignal:
    """Create a risk signal (typically by Reviewer Agent)."""
    risk = RiskSignal(
        id=str(uuid4()),
        project_id=risk_data.project_id,
        task_id=risk_data.task_id,
        subtask_id=risk_data.subtask_id,
        source=risk_data.source.value,
        severity=risk_data.severity.value,
        title=risk_data.title,
        description=risk_data.description,
        rationale=risk_data.rationale,
        recommended_action=risk_data.recommended_action,
    )
    db.add(risk)
    await db.commit()
    await db.refresh(risk)
    return risk


@risks_router.get("/project/{project_id}", response_model=list[RiskSignalResponse])
async def list_project_risks(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_resolved: bool = False,
) -> list[RiskSignal]:
    """List risk signals for a project."""
    query = select(RiskSignal).where(RiskSignal.project_id == project_id)
    if not include_resolved:
        query = query.where(RiskSignal.is_resolved == False)
    query = query.order_by(RiskSignal.created_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


@risks_router.post("/{risk_id}/resolve", response_model=RiskSignalResponse)
async def resolve_risk_signal(
    risk_id: str,
    resolve_data: RiskSignalResolve,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RiskSignal:
    """Resolve a risk signal."""
    result = await db.execute(select(RiskSignal).where(RiskSignal.id == risk_id))
    risk = result.scalar_one_or_none()

    if not risk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk signal not found")

    risk.is_resolved = True
    risk.resolved_at = datetime.utcnow()
    risk.resolved_by_id = current_user.id

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="risk_resolved",
        resource_type="risk_signal",
        resource_id=risk_id,
        details={"resolution_note": resolve_data.resolution_note},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(risk)
    return risk


# ============== Reviewer Routes ==============


@reviewer_router.get("/risks/{project_id}", response_model=list[RiskSignalResponse])
async def get_reviewer_risks(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RiskSignal]:
    """Get all risk signals for a project from the reviewer agent perspective."""
    result = await db.execute(
        select(RiskSignal)
        .where(RiskSignal.project_id == project_id)
        .order_by(
            RiskSignal.severity.desc(),
            RiskSignal.created_at.desc(),
        )
    )
    return list(result.scalars().all())


@reviewer_router.post(
    "/finalize/{task_id}",
    response_model=ReviewerFinalizeResponse,
)
async def finalize_task_review(
    task_id: str,
    body: ReviewerFinalizeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Run the Reviewer Agent on a completed task.

    Analyzes consistency, conflicts, quality, and returns merge-readiness.
    Creates RiskSignal rows for any findings.
    """
    from src.services.reviewer_service import get_reviewer_service

    # Verify task belongs to current user
    task_result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by_id == current_user.id)
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Verify project belongs to current user
    proj_result = await db.execute(
        select(Project).where(
            Project.id == body.project_id, Project.owner_id == current_user.id
        )
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Check usage limit
    paid_service = get_paid_service()
    effective_team_id = task.team_id or f"user_{current_user.id}"
    if not await paid_service.check_usage_limit(effective_team_id, db):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily usage limit exceeded",
        )

    reviewer = get_reviewer_service()
    try:
        result = await reviewer.finalize_task(task_id, body.project_id, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Track usage
    try:
        await paid_service.track_usage(
            db=db,
            team_id=effective_team_id,
            user_id=current_user.id,
            usage_type="reviewer_finalize",
            data={"task_id": task_id, "project_id": body.project_id},
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Usage tracking failed in reviewer: %s", e)

    await db.commit()
    return result
