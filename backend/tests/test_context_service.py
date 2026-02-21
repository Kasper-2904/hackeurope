"""Tests for SharedContextService (M2-T1)."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.context_service import SharedContextService
from src.storage.models import Project, TeamMember, User


# ============== Helpers ==============


def _make_user(db: AsyncSession) -> User:
    user = User(
        id=str(uuid4()),
        email=f"ctx-{uuid4().hex[:6]}@example.com",
        username=f"ctx-user-{uuid4().hex[:6]}",
        hashed_password="fakehash",
    )
    db.add(user)
    return user


async def _make_project(db: AsyncSession) -> Project:
    user = _make_user(db)
    project = Project(
        id=str(uuid4()),
        name="Context Test Project",
        description="A project for testing context service",
        goals=["ship MVP", "write tests"],
        owner_id=user.id,
        github_repo="owner/repo",
    )
    db.add(project)
    await db.flush()
    return project


async def _make_member(db: AsyncSession, project_id: str, user_id: str) -> TeamMember:
    member = TeamMember(
        id=str(uuid4()),
        user_id=user_id,
        project_id=project_id,
        role="developer",
        skills=["python", "fastapi"],
        capacity=1.0,
    )
    db.add(member)
    await db.flush()
    return member


# ============== Tests ==============


async def test_gather_context_returns_project(db_session: AsyncSession):
    """gather_context includes project data from DB."""
    project = await _make_project(db_session)
    service = SharedContextService()

    ctx = await service.gather_context(project.id, db_session)

    assert ctx["project"]["id"] == project.id
    assert ctx["project"]["name"] == "Context Test Project"
    assert "ship MVP" in ctx["project"]["goals"]


async def test_gather_context_includes_team_members(db_session: AsyncSession):
    """gather_context includes team members from DB."""
    project = await _make_project(db_session)
    user = _make_user(db_session)
    await db_session.flush()
    await _make_member(db_session, project.id, user.id)

    service = SharedContextService()
    ctx = await service.gather_context(project.id, db_session)

    assert len(ctx["team_members_db"]) == 1
    assert ctx["team_members_db"][0]["role"] == "developer"
    assert "python" in ctx["team_members_db"][0]["skills"]


async def test_gather_context_no_project(db_session: AsyncSession):
    """gather_context returns empty project when project_id not found."""
    service = SharedContextService()
    ctx = await service.gather_context("nonexistent-id", db_session)

    assert ctx["project"] == {}
    assert ctx["team_members_db"] == []
    assert ctx["tasks_db"] == []


async def test_gather_context_reads_static_files(db_session: AsyncSession, tmp_path: Path):
    """gather_context reads markdown files from context dir."""
    # Create a temp context dir with a file
    ctx_dir = tmp_path / "shared_context"
    ctx_dir.mkdir()
    (ctx_dir / "PROJECT_OVERVIEW.md").write_text("# My Project\nSome overview content here.")

    project = await _make_project(db_session)
    service = SharedContextService(context_dir=ctx_dir)
    ctx = await service.gather_context(project.id, db_session)

    assert "My Project" in ctx["project_overview"]


async def test_update_context_file(tmp_path: Path):
    """update_context_file writes to the correct path."""
    ctx_dir = tmp_path / "shared_context"
    ctx_dir.mkdir()

    service = SharedContextService(context_dir=ctx_dir)
    await service.update_context_file("TEAM_CONTEXT.md", "# Updated\nNew content")

    content = (ctx_dir / "TEAM_CONTEXT.md").read_text()
    assert "Updated" in content
    assert "New content" in content


async def test_gather_context_missing_static_file(db_session: AsyncSession, tmp_path: Path):
    """gather_context returns empty string for missing markdown files."""
    ctx_dir = tmp_path / "shared_context"
    ctx_dir.mkdir()
    # Don't create any files

    project = await _make_project(db_session)
    service = SharedContextService(context_dir=ctx_dir)
    ctx = await service.gather_context(project.id, db_session)

    assert ctx["project_overview"] == ""
    assert ctx["task_graph"] == ""
