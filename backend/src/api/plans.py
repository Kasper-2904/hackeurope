"""Plan routing endpoints."""

from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.schemas import (
    PlanCreate,
    PlanGenerate,
    PlanGenerateResponse,
    PlanReject,
    PlanResponse,
    PlanSubmitForApproval,
)
from src.core.state import PlanStatus
from src.storage.database import get_db
from src.storage.models import AuditLog, Plan, Project, Task, User

plans_router = APIRouter(prefix="/plans", tags=["Plans"])


@plans_router.post("/generate", response_model=PlanGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_plan(
    plan_data: PlanGenerate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Generate a plan for a task using the OA (Claude + shared context)."""
    from src.core.orchestrator import get_orchestrator

    # Look up the task — scoped to current user
    result = await db.execute(
        select(Task).where(Task.id == plan_data.task_id, Task.created_by_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Verify project exists and belongs to current user
    proj_result = await db.execute(
        select(Project).where(
            Project.id == plan_data.project_id, Project.owner_id == current_user.id
        )
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    orchestrator = get_orchestrator()
    result_data = await orchestrator.generate_plan(
        task_id=task.id,
        task_title=task.title,
        task_description=task.description or "",
        project_id=plan_data.project_id,
        db=db,
    )

    await db.commit()
    return result_data


@plans_router.post("/{plan_id}/approve", response_model=PlanResponse)
async def approve_plan(
    plan_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Plan:
    """Approve a plan (PM approval)."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    if plan.status != PlanStatus.PENDING_PM_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan must be in pending_pm_approval status to be approved",
        )

    plan.status = PlanStatus.APPROVED.value
    plan.approved_by_id = current_user.id
    plan.approved_at = datetime.utcnow()

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="plan_approved",
        resource_type="plan",
        resource_id=plan_id,
        details={"version": plan.version},
        previous_state={"status": PlanStatus.PENDING_PM_APPROVAL.value},
        new_state={"status": PlanStatus.APPROVED.value},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(plan)
    return plan


@plans_router.post("/{plan_id}/reject", response_model=PlanResponse)
async def reject_plan(
    plan_id: str,
    rejection: PlanReject,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Plan:
    """Reject a plan (PM rejection with reason)."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    if plan.status != PlanStatus.PENDING_PM_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan must be in pending_pm_approval status to be rejected",
        )

    plan.status = PlanStatus.REJECTED.value
    plan.rejection_reason = rejection.rejection_reason

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="plan_rejected",
        resource_type="plan",
        resource_id=plan_id,
        details={"version": plan.version, "reason": rejection.rejection_reason},
        previous_state={"status": PlanStatus.PENDING_PM_APPROVAL.value},
        new_state={"status": PlanStatus.REJECTED.value},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(plan)
    return plan


@plans_router.post("/{plan_id}/submit", response_model=PlanResponse)
async def submit_plan_for_approval(
    plan_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Plan:
    """Submit a draft plan for PM approval."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    if plan.status != PlanStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan must be in draft status to be submitted for approval",
        )

    plan.status = PlanStatus.PENDING_PM_APPROVAL.value

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="plan_submitted",
        resource_type="plan",
        resource_id=plan_id,
        details={"version": plan.version},
        previous_state={"status": PlanStatus.DRAFT.value},
        new_state={"status": PlanStatus.PENDING_PM_APPROVAL.value},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(plan)
    return plan


@plans_router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Plan:
    """Get a plan by ID."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    return plan
