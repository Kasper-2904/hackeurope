"""Teams routing endpoints."""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.schemas import (
    TeamCreate,
    TeamResponse,
    TeamMemberCreate,
    TeamMemberResponse,
    TeamMemberUpdate,
)
from src.storage.database import get_db
from src.storage.models import Team, TeamMember, Project, User

teams_router = APIRouter(prefix="/teams", tags=["Teams"])
team_members_router = APIRouter(prefix="/team-members", tags=["Team Members"])

# ============== Team Routes ==============


@teams_router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_data: TeamCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Team:
    """Create a new team."""
    team = Team(
        id=str(uuid4()),
        name=team_data.name,
        description=team_data.description,
        owner_id=current_user.id,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)

    return team


@teams_router.get("", response_model=list[TeamResponse])
async def list_teams(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Team]:
    """List teams owned by the current user."""
    result = await db.execute(select(Team).where(Team.owner_id == current_user.id))
    return list(result.scalars().all())


@teams_router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Team:
    """Get a team by ID."""
    result = await db.execute(
        select(Team).where(Team.id == team_id, Team.owner_id == current_user.id)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    return team


# ============== Team Member Routes ==============


@team_members_router.post(
    "", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED
)
async def add_team_member(
    member_data: TeamMemberCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamMember:
    """Add a team member to a project."""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(
            Project.id == member_data.project_id, Project.owner_id == current_user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    member = TeamMember(
        id=str(uuid4()),
        user_id=member_data.user_id,
        project_id=member_data.project_id,
        role=member_data.role.value,
        skills=member_data.skills,
        capacity=member_data.capacity,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@team_members_router.get("/project/{project_id}", response_model=list[TeamMemberResponse])
async def list_team_members(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TeamMember]:
    """List team members for a project."""
    result = await db.execute(select(TeamMember).where(TeamMember.project_id == project_id))
    return list(result.scalars().all())


@team_members_router.patch("/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: str,
    update_data: TeamMemberUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamMember:
    """Update a team member."""
    result = await db.execute(select(TeamMember).where(TeamMember.id == member_id))
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            if field == "role":
                setattr(member, field, value.value)
            else:
                setattr(member, field, value)

    await db.commit()
    await db.refresh(member)
    return member
