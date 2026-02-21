"""Tests for GitHub ingestion adapter (M1-T2)."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas_github import GitHubCIStatus, GitHubCommit, GitHubPullRequest
from src.services.github_service import (
    GitHubService,
    HttpxGitHubProvider,
    MockGitHubProvider,
    _parse_repo,
    normalize_ci_status,
    normalize_commit,
    normalize_pull_request,
)
from src.storage.models import GitHubContext, Project, RiskSignal, User


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


async def _make_project(db: AsyncSession, github_repo: str | None = "Kasper-2904/hackeurope") -> Project:
    user = _make_user(db)
    project = Project(
        id=str(uuid4()),
        name="Test Project",
        owner_id=user.id,
        github_repo=github_repo,
    )
    db.add(project)
    await db.flush()
    return project


# ============== parse_repo ==============


def test_parse_repo_slug():
    owner, repo = _parse_repo("Kasper-2904/hackeurope")
    assert owner == "Kasper-2904"
    assert repo == "hackeurope"


def test_parse_repo_full_url():
    owner, repo = _parse_repo("https://github.com/Kasper-2904/hackeurope")
    assert owner == "Kasper-2904"
    assert repo == "hackeurope"


def test_parse_repo_trailing_slash():
    owner, repo = _parse_repo("https://github.com/Kasper-2904/hackeurope/")
    assert owner == "Kasper-2904"
    assert repo == "hackeurope"


def test_parse_repo_invalid():
    with pytest.raises(ValueError, match="Cannot parse"):
        _parse_repo("just-a-name")


# ============== Normalizers ==============


def test_normalize_pull_request():
    now = datetime.now(timezone.utc).isoformat()
    raw = {
        "number": 42,
        "title": "feat: add auth",
        "state": "open",
        "user": {"login": "alice"},
        "created_at": now,
        "updated_at": now,
        "merged_at": None,
        "head": {"ref": "feature/auth"},
        "base": {"ref": "main"},
        "additions": 100,
        "deletions": 20,
        "changed_files": 5,
        "labels": [{"name": "enhancement"}],
        "mergeable_state": "dirty",
    }
    pr = normalize_pull_request(raw)
    assert pr.number == 42
    assert pr.author == "alice"
    assert pr.has_conflicts is True
    assert pr.labels == ["enhancement"]


def test_normalize_commit():
    now = datetime.now(timezone.utc).isoformat()
    raw = {
        "sha": "abc123",
        "commit": {
            "message": "fix: something",
            "author": {"name": "bob", "date": now},
        },
        "files": [{"filename": "a.py"}, {"filename": "b.py"}],
    }
    commit = normalize_commit(raw)
    assert commit.sha == "abc123"
    assert commit.author == "bob"
    assert commit.files_changed == 2


def test_normalize_ci_status():
    raw = {
        "name": "pytest",
        "status": "completed",
        "conclusion": "failure",
        "started_at": None,
        "completed_at": None,
        "pr_number": 42,
    }
    ci = normalize_ci_status(raw)
    assert ci.name == "pytest"
    assert ci.conclusion == "failure"
    assert ci.pr_number == 42


# ============== MockGitHubProvider ==============


async def test_mock_provider_returns_data():
    provider = MockGitHubProvider()
    prs = await provider.get_pull_requests("owner", "repo")
    commits = await provider.get_recent_commits("owner", "repo")
    ci = await provider.get_ci_status("owner", "repo")

    assert len(prs) == 2
    assert len(commits) == 2
    assert len(ci) == 2


# ============== GitHubService.sync_project ==============


async def test_sync_project_happy_path(db_session: AsyncSession):
    project = await _make_project(db_session)

    service = GitHubService(provider=MockGitHubProvider())
    result = await service.sync_project(project.id, db_session)

    assert result["project_id"] == project.id
    assert result["pull_requests_count"] == 2
    assert result["commits_count"] == 2
    assert result["ci_checks_count"] == 2
    # Mock data has 1 conflict PR + 1 CI failure = 2 risks
    assert result["risks_created"] == 2
    assert result["last_synced_at"] is not None


async def test_sync_project_creates_github_context(db_session: AsyncSession):
    project = await _make_project(db_session)
    service = GitHubService(provider=MockGitHubProvider())

    await service.sync_project(project.id, db_session)

    ctx = await service.get_context(project.id, db_session)
    assert ctx is not None
    assert len(ctx.pull_requests) == 2
    assert len(ctx.recent_commits) == 2
    assert len(ctx.ci_status) == 2
    assert ctx.sync_error is None


async def test_sync_project_no_github_repo(db_session: AsyncSession):
    project = await _make_project(db_session, github_repo=None)
    service = GitHubService(provider=MockGitHubProvider())

    with pytest.raises(ValueError, match="no github_repo configured"):
        await service.sync_project(project.id, db_session)


async def test_sync_project_not_found(db_session: AsyncSession):
    service = GitHubService(provider=MockGitHubProvider())

    with pytest.raises(ValueError, match="Project not found"):
        await service.sync_project("nonexistent-id", db_session)


async def test_sync_project_creates_risk_signals(db_session: AsyncSession):
    """Verify merge conflict -> HIGH risk, CI failure -> MEDIUM risk."""
    project = await _make_project(db_session)
    service = GitHubService(provider=MockGitHubProvider())

    await service.sync_project(project.id, db_session)

    from sqlalchemy import select

    result = await db_session.execute(
        select(RiskSignal).where(RiskSignal.project_id == project.id)
    )
    risks = list(result.scalars().all())

    assert len(risks) == 2

    sources = {r.source for r in risks}
    assert "merge_conflict" in sources
    assert "ci_failure" in sources

    severities = {r.source: r.severity for r in risks}
    assert severities["merge_conflict"] == "high"
    assert severities["ci_failure"] == "medium"


async def test_sync_project_is_idempotent(db_session: AsyncSession):
    """Syncing twice should not duplicate risk signals."""
    project = await _make_project(db_session)
    service = GitHubService(provider=MockGitHubProvider())

    await service.sync_project(project.id, db_session)
    await service.sync_project(project.id, db_session)

    from sqlalchemy import select

    result = await db_session.execute(
        select(RiskSignal).where(RiskSignal.project_id == project.id)
    )
    risks = list(result.scalars().all())
    assert len(risks) == 2  # Not 4 — dedup prevents duplicates


# ============== HttpxGitHubProvider ==============


def _mock_response(status_code: int = 200, json_data: Any = None, text: str = "") -> httpx.Response:
    """Create a mock httpx.Response with proper content."""
    import json as jsonlib

    content = jsonlib.dumps(json_data).encode() if json_data is not None else text.encode()
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": "application/json"} if json_data is not None else {},
        request=httpx.Request("GET", "https://api.github.com/test"),
    )


@pytest.fixture
def httpx_provider():
    """Create an HttpxGitHubProvider with a mocked httpx client."""
    provider = HttpxGitHubProvider(token="test-token")
    provider._client = AsyncMock(spec=httpx.AsyncClient)
    return provider


async def test_httpx_provider_fetches_prs(httpx_provider):
    """HttpxGitHubProvider fetches PR list then details for each."""
    now = datetime.now(timezone.utc).isoformat()
    pr_list_resp = _mock_response(json_data=[
        {"number": 1, "title": "PR one", "state": "open"},
    ])
    pr_detail_resp = _mock_response(json_data={
        "number": 1,
        "title": "PR one",
        "state": "open",
        "user": {"login": "alice"},
        "created_at": now,
        "updated_at": now,
        "head": {"ref": "feat/one"},
        "base": {"ref": "main"},
        "additions": 50,
        "deletions": 10,
        "changed_files": 3,
        "labels": [],
        "mergeable_state": "clean",
    })
    httpx_provider._client.get = AsyncMock(side_effect=[pr_list_resp, pr_detail_resp])

    prs = await httpx_provider.get_pull_requests("owner", "repo")

    assert len(prs) == 1
    assert prs[0]["additions"] == 50
    assert prs[0]["mergeable_state"] == "clean"
    assert httpx_provider._client.get.call_count == 2


async def test_httpx_provider_fetches_commits(httpx_provider):
    """HttpxGitHubProvider fetches commit list."""
    now = datetime.now(timezone.utc).isoformat()
    resp = _mock_response(json_data=[
        {
            "sha": "abc123",
            "commit": {"message": "feat: something", "author": {"name": "bob", "date": now}},
        },
    ])
    httpx_provider._client.get = AsyncMock(return_value=resp)

    commits = await httpx_provider.get_recent_commits("owner", "repo", limit=10)

    assert len(commits) == 1
    assert commits[0]["sha"] == "abc123"


async def test_httpx_provider_fetches_ci_status(httpx_provider):
    """HttpxGitHubProvider fetches Actions runs and maps to our schema."""
    resp = _mock_response(json_data={
        "workflow_runs": [
            {
                "name": "CI",
                "status": "completed",
                "conclusion": "success",
                "run_started_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:05:00Z",
                "pull_requests": [{"number": 7}],
            },
        ],
    })
    httpx_provider._client.get = AsyncMock(return_value=resp)

    ci = await httpx_provider.get_ci_status("owner", "repo")

    assert len(ci) == 1
    assert ci[0]["name"] == "CI"
    assert ci[0]["conclusion"] == "success"
    assert ci[0]["pr_number"] == 7


async def test_httpx_provider_handles_auth_error(httpx_provider):
    """HttpxGitHubProvider raises ValueError on 401."""
    resp = _mock_response(status_code=401, json_data={"message": "Bad credentials"})
    httpx_provider._client.get = AsyncMock(return_value=resp)

    with pytest.raises(ValueError, match="authentication failed"):
        await httpx_provider.get_pull_requests("owner", "repo")


async def test_real_provider_used_when_token_set():
    """get_github_service() uses HttpxGitHubProvider when GITHUB_TOKEN is set."""
    import src.api.github as github_module

    # Reset singleton
    github_module._github_service = None

    mock_settings = MagicMock(
        github_token="ghp_test123",
        github_api_base_url="https://api.github.com",
    )
    with patch("src.api.github.get_settings", return_value=mock_settings):
        service = github_module.get_github_service()

    assert isinstance(service._provider, HttpxGitHubProvider)

    # Clean up singleton
    github_module._github_service = None
