"""Tests for M5-T10: GitHub sync auto-refreshes shared context MD files."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.context_service import SharedContextService
from src.services.github_service import GitHubService, MockGitHubProvider
from src.storage.models import Agent, GitHubContext, Project, RiskSignal, Task, TeamMember, User


# ============== Helpers ==============


def _make_user(db: AsyncSession) -> User:
    user = User(
        id=str(uuid4()),
        email=f"test-{uuid4().hex[:6]}@example.com",
        username=f"testuser-{uuid4().hex[:6]}",
        hashed_password="fakehash",
    )
    db.add(user)
    return user


async def _make_project(
    db: AsyncSession,
    github_repo: str = "Kasper-2904/hackeurope",
    name: str = "Test Project",
    description: str = "A test project for context refresh",
    goals: list | None = None,
) -> Project:
    user = _make_user(db)
    project = Project(
        id=str(uuid4()),
        name=name,
        description=description,
        owner_id=user.id,
        github_repo=github_repo,
        goals=goals or ["Ship MVP", "Pass all tests"],
    )
    db.add(project)
    await db.flush()
    return project


# ============== SharedContextService.refresh_context_files ==============


async def test_refresh_creates_all_context_files(db_session: AsyncSession):
    """refresh_context_files writes 5 MD files from DB state."""
    project = await _make_project(db_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        svc = SharedContextService(context_dir=Path(tmpdir))
        result = await svc.refresh_context_files(project.id, db_session)

    assert len(result) == 5
    assert "PROJECT_OVERVIEW.md" in result
    assert "INTEGRATIONS_GITHUB.md" in result
    assert "TASK_GRAPH.md" in result
    assert "TEAM_MEMBERS.md" in result
    assert "HOSTED_AGENTS.md" in result


async def test_refresh_populates_project_overview(db_session: AsyncSession):
    """PROJECT_OVERVIEW.md contains project name, description, goals."""
    project = await _make_project(
        db_session,
        name="My Project",
        description="Building something cool",
        goals=["Goal A", "Goal B"],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        svc = SharedContextService(context_dir=Path(tmpdir))
        await svc.refresh_context_files(project.id, db_session)

        content = (Path(tmpdir) / "PROJECT_OVERVIEW.md").read_text()

    assert "My Project" in content
    assert "Building something cool" in content
    assert "Goal A" in content
    assert "Goal B" in content


async def test_refresh_populates_github_integration(db_session: AsyncSession):
    """INTEGRATIONS_GITHUB.md contains PR/commit/CI data after sync."""
    project = await _make_project(db_session)

    # Sync GitHub data first (uses mock provider)
    github_svc = GitHubService(provider=MockGitHubProvider())
    await github_svc.sync_project(project.id, db_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        svc = SharedContextService(context_dir=Path(tmpdir))
        await svc.refresh_context_files(project.id, db_session)

        content = (Path(tmpdir) / "INTEGRATIONS_GITHUB.md").read_text()

    # Should contain PR data from mock
    assert "PR Status Snapshot" in content
    assert "#42" in content
    assert "add user authentication" in content
    # Should contain CI data
    assert "CI Status Snapshot" in content
    assert "pytest" in content
    # Should flag merge constraints
    assert "Merge Constraints" in content
    assert "merge conflicts" in content
    assert "CI check" in content


async def test_refresh_github_no_sync_shows_placeholder(db_session: AsyncSession):
    """INTEGRATIONS_GITHUB.md shows placeholder when no sync has run."""
    project = await _make_project(db_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        svc = SharedContextService(context_dir=Path(tmpdir))
        await svc.refresh_context_files(project.id, db_session)

        content = (Path(tmpdir) / "INTEGRATIONS_GITHUB.md").read_text()

    assert "No GitHub data synced yet" in content


async def test_refresh_populates_task_graph_with_risks(db_session: AsyncSession):
    """TASK_GRAPH.md shows open risks after GitHub sync creates them."""
    project = await _make_project(db_session)

    # Sync creates risk signals (1 conflict + 1 CI failure)
    github_svc = GitHubService(provider=MockGitHubProvider())
    await github_svc.sync_project(project.id, db_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        svc = SharedContextService(context_dir=Path(tmpdir))
        await svc.refresh_context_files(project.id, db_session)

        content = (Path(tmpdir) / "TASK_GRAPH.md").read_text()

    assert "Open Risks" in content
    assert "Merge conflict" in content or "CI check" in content


async def test_refresh_nonexistent_project_returns_empty(db_session: AsyncSession):
    """refresh_context_files returns empty dict for unknown project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = SharedContextService(context_dir=Path(tmpdir))
        result = await svc.refresh_context_files("nonexistent-id", db_session)

    assert result == {}


# ============== GitHubService.sync_project auto-refresh ==============


async def test_sync_project_auto_refreshes_context_files(db_session: AsyncSession):
    """sync_project result includes context_files_refreshed count."""
    project = await _make_project(db_session)

    service = GitHubService(provider=MockGitHubProvider())
    result = await service.sync_project(project.id, db_session)

    assert result["context_files_refreshed"] == 5


async def test_sync_project_writes_github_md(db_session: AsyncSession):
    """After sync, the context service writes INTEGRATIONS_GITHUB.md with real data."""
    project = await _make_project(db_session)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the context service used by GitHubService to write to temp dir
        from unittest.mock import patch
        from src.services.context_service import SharedContextService

        patched_svc = SharedContextService(context_dir=Path(tmpdir))
        service = GitHubService(provider=MockGitHubProvider())
        service._context_service = patched_svc

        await service.sync_project(project.id, db_session)

        content = (Path(tmpdir) / "INTEGRATIONS_GITHUB.md").read_text()
        assert "PR Status Snapshot" in content
        assert "#42" in content


# ============== Renderer unit tests ==============


def test_render_project_overview_with_empty_goals():
    """Renderer handles project with no goals/milestones."""
    from unittest.mock import MagicMock

    project = MagicMock()
    project.name = "Test"
    project.description = "Desc"
    project.goals = []
    project.milestones = None
    project.github_repo = "owner/repo"

    content = SharedContextService._render_project_overview(project)

    assert "Test" in content
    assert "No goals defined" in content
    assert "No milestones defined" in content


def test_render_github_integration_no_context():
    """Renderer handles missing GitHub context gracefully."""
    from unittest.mock import MagicMock

    project = MagicMock()
    project.github_repo = "owner/repo"

    content = SharedContextService._render_github_integration(project, None)

    assert "No GitHub data synced yet" in content
    assert "owner/repo" in content


def test_render_github_integration_with_data():
    """Renderer formats PR/commit/CI data into readable markdown."""
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    project = MagicMock()
    project.github_repo = "owner/repo"

    ctx = MagicMock()
    ctx.last_synced_at = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
    ctx.pull_requests = [
        {
            "number": 1,
            "title": "feat: add auth",
            "head_branch": "feat/auth",
            "base_branch": "main",
            "author": "alice",
            "additions": 100,
            "deletions": 10,
            "changed_files": 5,
            "labels": ["enhancement"],
            "has_conflicts": True,
        }
    ]
    ctx.recent_commits = [
        {"sha": "abc1234", "message": "fix: bug", "author": "bob"}
    ]
    ctx.ci_status = [
        {"name": "pytest", "conclusion": "failure", "pr_number": 1}
    ]

    content = SharedContextService._render_github_integration(project, ctx)

    assert "#1" in content
    assert "feat: add auth" in content
    assert "CONFLICT" in content
    assert "abc1234" in content
    assert "FAIL" in content
    assert "merge conflicts" in content
    assert "CI check" in content


def test_render_task_graph_empty():
    """Renderer handles no tasks and no risks."""
    content = SharedContextService._render_task_graph([], [])
    assert "No tasks linked" in content
    assert "No open risks" in content
