"""Tests for teams and team members API endpoints."""

import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.teams import create_team, list_teams, get_team, add_team_member, list_team_members, update_team_member
from src.api.schemas import TeamCreate, TeamMemberCreate, TeamMemberUpdate
from src.core.state import UserRole
from src.storage.models import Project, User


async def _make_user(db: AsyncSession, username: str, email: str) -> User:
    user = User(
        id=str(uuid4()),
        username=username,
        email=email,
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_project(db: AsyncSession, owner: User) -> Project:
    project = Project(id=str(uuid4()), name="Test Project", owner_id=owner.id)
    db.add(project)
    await db.flush()
    return project


# ============== Team Tests ==============


class TestTeams:
    @pytest.mark.asyncio
    async def test_create_team(self, db_session: AsyncSession):
        user = await _make_user(db_session, "team_owner", "team_owner@test.com")
        await db_session.commit()

        team = await create_team(
            team_data=TeamCreate(name="My Team", description="A test team"),
            current_user=user,
            db=db_session,
        )

        assert team.name == "My Team"
        assert team.description == "A test team"
        assert team.owner_id == user.id

    @pytest.mark.asyncio
    async def test_list_teams_returns_only_owned(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "owner", "owner@test.com")
        other = await _make_user(db_session, "other", "other@test.com")
        await db_session.commit()

        await create_team(TeamCreate(name="Owner Team"), current_user=owner, db=db_session)
        await create_team(TeamCreate(name="Other Team"), current_user=other, db=db_session)

        teams = await list_teams(current_user=owner, db=db_session)
        names = {t.name for t in teams}

        assert "Owner Team" in names
        assert "Other Team" not in names

    @pytest.mark.asyncio
    async def test_get_team_success(self, db_session: AsyncSession):
        user = await _make_user(db_session, "getter", "getter@test.com")
        await db_session.commit()

        team = await create_team(TeamCreate(name="Get Me"), current_user=user, db=db_session)
        fetched = await get_team(team_id=team.id, current_user=user, db=db_session)

        assert fetched.id == team.id
        assert fetched.name == "Get Me"

    @pytest.mark.asyncio
    async def test_get_team_not_found(self, db_session: AsyncSession):
        user = await _make_user(db_session, "nope", "nope@test.com")
        await db_session.commit()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_team(team_id="nonexistent", current_user=user, db=db_session)

        assert exc_info.value.status_code == 404


# ============== Team Member Tests ==============


class TestTeamMembers:
    @pytest.mark.asyncio
    async def test_add_team_member(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "pm_owner", "pm_owner@test.com")
        dev = await _make_user(db_session, "dev", "dev@test.com")
        project = await _make_project(db_session, owner)
        await db_session.commit()

        member = await add_team_member(
            member_data=TeamMemberCreate(
                user_id=dev.id,
                project_id=project.id,
                role=UserRole.DEVELOPER,
                skills=["python"],
                capacity=1.0,
            ),
            current_user=owner,
            db=db_session,
        )

        assert member.user_id == dev.id
        assert member.project_id == project.id
        assert member.role == UserRole.DEVELOPER.value

    @pytest.mark.asyncio
    async def test_add_member_to_unowned_project_404(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "real_owner", "real@test.com")
        intruder = await _make_user(db_session, "intruder", "intruder@test.com")
        dev = await _make_user(db_session, "dev2", "dev2@test.com")
        project = await _make_project(db_session, owner)
        await db_session.commit()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await add_team_member(
                member_data=TeamMemberCreate(
                    user_id=dev.id, project_id=project.id, role=UserRole.DEVELOPER,
                ),
                current_user=intruder,
                db=db_session,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_team_members(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "list_owner", "list_owner@test.com")
        dev = await _make_user(db_session, "list_dev", "list_dev@test.com")
        project = await _make_project(db_session, owner)
        await db_session.commit()

        await add_team_member(
            member_data=TeamMemberCreate(
                user_id=dev.id, project_id=project.id, role=UserRole.DEVELOPER,
            ),
            current_user=owner,
            db=db_session,
        )

        members = await list_team_members(
            project_id=project.id, current_user=owner, db=db_session
        )

        assert len(members) == 1
        assert members[0].user_id == dev.id

    @pytest.mark.asyncio
    async def test_update_team_member(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "upd_owner", "upd_owner@test.com")
        dev = await _make_user(db_session, "upd_dev", "upd_dev@test.com")
        project = await _make_project(db_session, owner)
        await db_session.commit()

        member = await add_team_member(
            member_data=TeamMemberCreate(
                user_id=dev.id, project_id=project.id, role=UserRole.DEVELOPER,
            ),
            current_user=owner,
            db=db_session,
        )

        updated = await update_team_member(
            member_id=member.id,
            update_data=TeamMemberUpdate(role=UserRole.ADMIN, capacity=0.5),
            current_user=owner,
            db=db_session,
        )

        assert updated.role == UserRole.ADMIN.value
        assert updated.capacity == 0.5
