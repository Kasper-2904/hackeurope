"""Tests for project API endpoints."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.projects import (
    create_project,
    get_project,
    list_projects,
    list_project_tasks,
    list_project_allowed_agents,
    add_project_allowed_agent,
)
from src.api.schemas import ProjectCreate
from src.core.state import AgentStatus, TaskStatus, PlanStatus
from src.storage.models import Agent, Plan, Project, Task, TeamMember, User


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


async def _make_agent(db: AsyncSession, owner: User) -> Agent:
    agent = Agent(
        id=str(uuid4()),
        name="Test Agent",
        role="coder",
        inference_endpoint="https://test.example.com",
        owner_id=owner.id,
        status=AgentStatus.ONLINE,
    )
    db.add(agent)
    await db.flush()
    return agent


class TestProjects:
    @pytest.mark.asyncio
    async def test_create_project(self, db_session: AsyncSession):
        user = await _make_user(db_session, "creator", "creator@test.com")
        await db_session.commit()

        project = await create_project(
            project_data=ProjectCreate(
                name="New Project",
                description="A test project",
                goals=["Ship fast"],
            ),
            current_user=user,
            db=db_session,
        )

        assert project.name == "New Project"
        assert project.owner_id == user.id
        assert project.goals == ["Ship fast"]

    @pytest.mark.asyncio
    async def test_list_projects_returns_owned(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "owner_user", "owner@example.com")
        await db_session.commit()

        db_session.add(Project(id=str(uuid4()), name="Project A", owner_id=owner.id))
        db_session.add(Project(id=str(uuid4()), name="Project B", owner_id=owner.id))
        await db_session.commit()

        projects = await list_projects(current_user=owner, db=db_session)
        names = {p.name for p in projects}

        assert "Project A" in names
        assert "Project B" in names

    @pytest.mark.asyncio
    async def test_list_projects_returns_member_projects(self, db_session: AsyncSession):
        owner = await _make_user(db_session, "proj_owner", "proj_owner@test.com")
        member = await _make_user(db_session, "proj_member", "proj_member@test.com")
        project = Project(id=str(uuid4()), name="Member Project", owner_id=owner.id)
        db_session.add(project)
        await db_session.flush()

        tm = TeamMember(
            id=str(uuid4()),
            user_id=member.id,
            project_id=project.id,
            role="developer",
        )
        db_session.add(tm)
        await db_session.commit()

        projects = await list_projects(current_user=member, db=db_session)
        names = {p.name for p in projects}

        assert "Member Project" in names

    @pytest.mark.asyncio
    async def test_get_project(self, db_session: AsyncSession):
        user = await _make_user(db_session, "getter", "getter@test.com")
        await db_session.commit()

        project = await create_project(
            project_data=ProjectCreate(name="Get Me"),
            current_user=user,
            db=db_session,
        )

        fetched = await get_project(
            project_id=project.id, current_user=user, db=db_session
        )

        assert fetched.id == project.id

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, db_session: AsyncSession):
        user = await _make_user(db_session, "nope", "nope@test.com")
        await db_session.commit()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_project(
                project_id="nonexistent", current_user=user, db=db_session
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_project_tasks(self, db_session: AsyncSession):
        user = await _make_user(db_session, "task_owner", "task_owner@test.com")
        project = Project(id=str(uuid4()), name="Task Project", owner_id=user.id)
        db_session.add(project)

        task = Task(
            id=str(uuid4()),
            title="Linked Task",
            task_type="code_generation",
            status=TaskStatus.PENDING,
            created_by_id=user.id,
        )
        db_session.add(task)
        await db_session.flush()

        plan = Plan(
            id=str(uuid4()),
            task_id=task.id,
            project_id=project.id,
            plan_data={"steps": ["do thing"]},
            status=PlanStatus.DRAFT.value,
        )
        db_session.add(plan)
        await db_session.commit()

        tasks = await list_project_tasks(
            project_id=project.id, current_user=user, db=db_session
        )

        assert len(tasks) == 1
        assert tasks[0].title == "Linked Task"


class TestProjectAllowlist:
    @pytest.mark.asyncio
    async def test_add_and_list_allowed_agent(self, db_session: AsyncSession):
        user = await _make_user(db_session, "allow_owner", "allow@test.com")
        project = Project(id=str(uuid4()), name="Allow Project", owner_id=user.id)
        db_session.add(project)
        agent = await _make_agent(db_session, user)
        await db_session.commit()

        allowed = await add_project_allowed_agent(
            project_id=project.id,
            agent_id=agent.id,
            current_user=user,
            db=db_session,
        )

        assert allowed.project_id == project.id
        assert allowed.agent_id == agent.id

        # List should return it
        agents = await list_project_allowed_agents(
            project_id=project.id, current_user=user, db=db_session
        )

        assert len(agents) == 1
