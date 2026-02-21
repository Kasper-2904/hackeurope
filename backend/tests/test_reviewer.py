"""Tests for ReviewerService (M2-T1)."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.reviewer_service import ReviewerService
from src.storage.models import Project, RiskSignal, Task, User


# ============== Helpers ==============


def _make_user(db: AsyncSession) -> User:
    user = User(
        id=str(uuid4()),
        email=f"rev-{uuid4().hex[:6]}@example.com",
        username=f"rev-user-{uuid4().hex[:6]}",
        hashed_password="fakehash",
    )
    db.add(user)
    return user


async def _make_project(db: AsyncSession) -> Project:
    user = _make_user(db)
    project = Project(
        id=str(uuid4()),
        name="Reviewer Test Project",
        owner_id=user.id,
    )
    db.add(project)
    await db.flush()
    return project


async def _make_task(db: AsyncSession, user_id: str) -> Task:
    task = Task(
        id=str(uuid4()),
        title="Build search feature",
        description="Full-text search for projects",
        task_type="code_generation",
        created_by_id=user_id,
    )
    db.add(task)
    await db.flush()
    return task


# ============== Tests ==============


MOCK_REVIEW_RESPONSE = {
    "merge_ready": True,
    "findings": [
        {
            "title": "Missing index on search column",
            "severity": "medium",
            "is_blocker": False,
            "description": "The search query may be slow without a DB index.",
            "recommended_action": "Add an index to the search column.",
        },
    ],
    "summary": "Task looks good overall. One non-blocking performance suggestion.",
    "context_updates": "Search feature added — watch for query performance.",
}


async def test_reviewer_happy_path(db_session: AsyncSession):
    """Reviewer analyzes task and returns findings + merge readiness."""
    project = await _make_project(db_session)
    user = (await db_session.execute(select(User))).scalars().first()
    task = await _make_task(db_session, user.id)

    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(return_value=MOCK_REVIEW_RESPONSE)

    reviewer = ReviewerService(llm=mock_llm)
    result = await reviewer.finalize_task(task.id, project.id, db_session)

    assert result["merge_ready"] is True
    assert len(result["findings"]) == 1
    assert result["findings"][0]["title"] == "Missing index on search column"
    assert result["risks_created"] == 1
    assert "looks good" in result["summary"]


async def test_reviewer_creates_risk_signals(db_session: AsyncSession):
    """Reviewer persists findings as RiskSignal rows."""
    project = await _make_project(db_session)
    user = (await db_session.execute(select(User))).scalars().first()
    task = await _make_task(db_session, user.id)

    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(return_value=MOCK_REVIEW_RESPONSE)

    reviewer = ReviewerService(llm=mock_llm)
    await reviewer.finalize_task(task.id, project.id, db_session)
    await db_session.flush()

    result = await db_session.execute(
        select(RiskSignal).where(
            RiskSignal.project_id == project.id,
            RiskSignal.source == "reviewer",
        )
    )
    risks = list(result.scalars().all())

    assert len(risks) == 1
    assert risks[0].severity == "medium"
    assert risks[0].task_id == task.id
    assert "index" in risks[0].title.lower()


async def test_reviewer_handles_llm_failure(db_session: AsyncSession):
    """Reviewer returns graceful error when LLM call fails."""
    project = await _make_project(db_session)
    user = (await db_session.execute(select(User))).scalars().first()
    task = await _make_task(db_session, user.id)

    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(side_effect=RuntimeError("Claude is down"))

    reviewer = ReviewerService(llm=mock_llm)
    result = await reviewer.finalize_task(task.id, project.id, db_session)

    assert result["merge_ready"] is False
    assert "Claude is down" in result["summary"]
    assert result["error"] is not None


async def test_reviewer_task_not_found(db_session: AsyncSession):
    """Reviewer raises ValueError when task doesn't exist."""
    project = await _make_project(db_session)

    mock_llm = AsyncMock()
    reviewer = ReviewerService(llm=mock_llm)

    with pytest.raises(ValueError, match="Task not found"):
        await reviewer.finalize_task("nonexistent-id", project.id, db_session)


async def test_reviewer_blocker_findings(db_session: AsyncSession):
    """Reviewer can report blocker findings that prevent merge."""
    project = await _make_project(db_session)
    user = (await db_session.execute(select(User))).scalars().first()
    task = await _make_task(db_session, user.id)

    blocker_response = {
        "merge_ready": False,
        "findings": [
            {
                "title": "SQL injection vulnerability",
                "severity": "critical",
                "is_blocker": True,
                "description": "User input is not sanitized in search query.",
                "recommended_action": "Use parameterized queries.",
            },
        ],
        "summary": "Critical security issue blocks merge.",
    }

    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(return_value=blocker_response)

    reviewer = ReviewerService(llm=mock_llm)
    result = await reviewer.finalize_task(task.id, project.id, db_session)

    assert result["merge_ready"] is False
    assert result["findings"][0]["is_blocker"] is True
    assert result["risks_created"] == 1

    # Verify critical severity persisted
    await db_session.flush()
    risk_result = await db_session.execute(
        select(RiskSignal).where(RiskSignal.task_id == task.id)
    )
    risk = risk_result.scalars().first()
    assert risk.severity == "critical"
