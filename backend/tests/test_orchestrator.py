"""Tests for the LangGraph orchestrator (M2-T1)."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.orchestrator import Orchestrator, _build_context_summary
from src.storage.models import Plan, Project, Task, User


# ============== Helpers ==============


def _make_user(db: AsyncSession) -> User:
    user = User(
        id=str(uuid4()),
        email=f"oa-{uuid4().hex[:6]}@example.com",
        username=f"oa-user-{uuid4().hex[:6]}",
        hashed_password="fakehash",
    )
    db.add(user)
    return user


async def _make_project(db: AsyncSession) -> Project:
    user = _make_user(db)
    project = Project(
        id=str(uuid4()),
        name="OA Test Project",
        description="Testing the orchestrator",
        owner_id=user.id,
    )
    db.add(project)
    await db.flush()
    return project


async def _make_task(db: AsyncSession, user_id: str) -> Task:
    task = Task(
        id=str(uuid4()),
        title="Implement login endpoint",
        description="Build a JWT login endpoint with validation",
        task_type="code_generation",
        created_by_id=user_id,
    )
    db.add(task)
    await db.flush()
    return task


# ============== Tests ==============


MOCK_PLAN_RESPONSE = {
    "subtasks": [
        {
            "title": "Create auth router",
            "description": "Build FastAPI router with /login endpoint",
            "agent_type": "coder",
            "assignee_role": "developer",
            "priority": 1,
            "risk_flags": [],
        },
        {
            "title": "Add JWT tests",
            "description": "Write pytest tests for the login flow",
            "agent_type": "tester",
            "assignee_role": "developer",
            "priority": 2,
            "risk_flags": [],
        },
    ],
    "rationale": "Standard auth implementation with test coverage.",
}


async def test_orchestrator_generates_plan(db_session: AsyncSession):
    """Happy path: orchestrator gathers context, calls LLM, persists plan."""
    project = await _make_project(db_session)
    user = (await db_session.execute(select(User))).scalars().first()
    task = await _make_task(db_session, user.id)

    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(return_value=MOCK_PLAN_RESPONSE)

    with patch("src.core.orchestrator.get_llm_service", return_value=mock_llm):
        orchestrator = Orchestrator()
        result = await orchestrator.generate_plan(
            task_id=task.id,
            task_title=task.title,
            task_description=task.description,
            project_id=project.id,
            db=db_session,
        )

    assert result["status"] == "persisted"
    assert result["plan_id"] is not None
    assert len(result["plan_data"]["subtasks"]) == 2
    assert result["rationale"] == "Standard auth implementation with test coverage."

    # Verify plan was persisted
    plan_result = await db_session.execute(select(Plan).where(Plan.id == result["plan_id"]))
    plan = plan_result.scalar_one_or_none()
    assert plan is not None
    assert plan.status == "draft"
    assert plan.task_id == task.id
    assert plan.project_id == project.id


async def test_orchestrator_handles_llm_failure(db_session: AsyncSession):
    """Orchestrator returns failed status when LLM call errors."""
    project = await _make_project(db_session)
    user = (await db_session.execute(select(User))).scalars().first()
    task = await _make_task(db_session, user.id)

    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(side_effect=RuntimeError("API timeout"))

    with patch("src.core.orchestrator.get_llm_service", return_value=mock_llm):
        orchestrator = Orchestrator()
        result = await orchestrator.generate_plan(
            task_id=task.id,
            task_title=task.title,
            task_description=task.description,
            project_id=project.id,
            db=db_session,
        )

    assert result["status"] == "failed"
    assert "API timeout" in result["error"]
    assert result["plan_id"] is None


async def test_orchestrator_handles_bad_llm_response(db_session: AsyncSession):
    """Orchestrator fails gracefully when LLM returns invalid structure."""
    project = await _make_project(db_session)
    user = (await db_session.execute(select(User))).scalars().first()
    task = await _make_task(db_session, user.id)

    # Missing required 'subtasks' key
    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(return_value={"summary": "no subtasks here"})

    with patch("src.core.orchestrator.get_llm_service", return_value=mock_llm):
        orchestrator = Orchestrator()
        result = await orchestrator.generate_plan(
            task_id=task.id,
            task_title=task.title,
            task_description=task.description,
            project_id=project.id,
            db=db_session,
        )

    assert result["status"] == "failed"
    assert "subtasks" in result["error"]


# ============== Context Summary Tests ==============


def test_build_context_summary_with_project():
    """_build_context_summary includes project info."""
    ctx = {
        "project": {"name": "TestApp", "description": "A test app", "goals": ["ship it"]},
        "team_members_db": [],
        "tasks_db": [],
        "github_context": {},
        "open_risks": [],
    }
    summary = _build_context_summary(ctx)
    assert "TestApp" in summary
    assert "ship it" in summary


def test_build_context_summary_empty():
    """_build_context_summary handles empty context gracefully."""
    ctx = {
        "project": {},
        "team_members_db": [],
        "tasks_db": [],
        "github_context": {},
        "open_risks": [],
    }
    summary = _build_context_summary(ctx)
    assert "No project context" in summary


def test_build_context_summary_with_risks():
    """_build_context_summary includes risk information."""
    ctx = {
        "project": {"name": "Proj"},
        "team_members_db": [],
        "tasks_db": [],
        "github_context": {},
        "open_risks": [
            {"id": "r1", "severity": "high", "title": "Merge conflict in auth", "description": ""},
        ],
    }
    summary = _build_context_summary(ctx)
    assert "Merge conflict" in summary
    assert "high" in summary
