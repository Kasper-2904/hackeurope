"""Dashboard routing endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.schemas import (
    DeveloperDashboardResponse,
    PMDashboardResponse,
)
from src.storage.database import get_db
from src.storage.models import Plan, Project, RiskSignal, Subtask, Task, TeamMember, User

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboards"])


@dashboard_router.get("/pm/{project_id}", response_model=PMDashboardResponse)
async def pm_dashboard(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get PM dashboard data."""
    from src.core.state import RiskSeverity

    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Get team members
    members_result = await db.execute(select(TeamMember).where(TeamMember.project_id == project_id))
    team_members = list(members_result.scalars().all())

    # Get tasks by status (tasks linked to project via plans)
    plans_result = await db.execute(
        select(Plan).where(Plan.project_id == project_id).order_by(Plan.created_at.desc()).limit(10)
    )
    recent_plans = list(plans_result.scalars().all())

    # Get open risks
    risks_result = await db.execute(
        select(RiskSignal)
        .where(
            RiskSignal.project_id == project_id,
            RiskSignal.is_resolved == False,
        )
        .order_by(RiskSignal.created_at.desc())
    )
    open_risks = list(risks_result.scalars().all())

    # Critical alerts are high/critical severity unresolved risks
    critical_alerts = [
        r
        for r in open_risks
        if r.severity in [RiskSeverity.HIGH.value, RiskSeverity.CRITICAL.value]
    ]

    return {
        "project_id": project_id,
        "project": project,
        "team_members": team_members,
        "tasks_by_status": {},  # TODO: Aggregate from tasks linked to project
        "recent_plans": recent_plans,
        "open_risks": open_risks,
        "critical_alerts": critical_alerts,
    }


@dashboard_router.get("/developer/{user_id}", response_model=DeveloperDashboardResponse)
async def developer_dashboard(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get developer dashboard data."""
    from src.core.state import SubtaskStatus

    # Ensure user can only access their own dashboard (or is admin)
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's dashboard",
        )

    # Get tasks assigned to this user (as creator for now)
    tasks_result = await db.execute(
        select(Task).where(Task.created_by_id == user_id).order_by(Task.created_at.desc())
    )
    assigned_tasks = list(tasks_result.scalars().all())

    # Get team memberships for this user
    memberships_result = await db.execute(select(TeamMember).where(TeamMember.user_id == user_id))
    memberships = list(memberships_result.scalars().all())
    member_ids = [m.id for m in memberships]

    # Get subtasks assigned to user via team memberships
    assigned_subtasks = []
    pending_reviews = []
    if member_ids:
        subtasks_result = await db.execute(
            select(Subtask).where(Subtask.assignee_id.in_(member_ids))
        )
        all_subtasks = list(subtasks_result.scalars().all())
        assigned_subtasks = [s for s in all_subtasks if s.status != SubtaskStatus.IN_REVIEW.value]
        pending_reviews = [s for s in all_subtasks if s.status == SubtaskStatus.IN_REVIEW.value]

    # Get recent risks for projects user is part of
    project_ids = [m.project_id for m in memberships]
    recent_risks = []
    if project_ids:
        risks_result = await db.execute(
            select(RiskSignal)
            .where(
                RiskSignal.project_id.in_(project_ids),
                RiskSignal.is_resolved == False,
            )
            .order_by(RiskSignal.created_at.desc())
            .limit(10)
        )
        recent_risks = list(risks_result.scalars().all())

    # Calculate workload
    workload = sum(m.current_load for m in memberships) / max(len(memberships), 1)

    return {
        "user_id": user_id,
        "assigned_tasks": assigned_tasks,
        "assigned_subtasks": assigned_subtasks,
        "pending_reviews": pending_reviews,
        "recent_risks": recent_risks,
        "workload": workload,
    }
