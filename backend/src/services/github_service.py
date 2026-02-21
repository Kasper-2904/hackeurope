"""GitHub ingestion service with swappable data provider."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from src.api.schemas_github import GitHubCIStatus, GitHubCommit, GitHubPullRequest
from src.core.state import RiskSeverity, RiskSource
from src.storage.models import GitHubContext, Project, RiskSignal


# ============== Provider Protocol ==============


class GitHubDataProvider(Protocol):
    """Protocol for fetching GitHub data. Swap MockGitHubProvider for HttpxGitHubProvider later."""

    async def get_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]: ...

    async def get_recent_commits(
        self, owner: str, repo: str, limit: int = 20
    ) -> list[dict[str, Any]]: ...

    async def get_ci_status(self, owner: str, repo: str) -> list[dict[str, Any]]: ...


# ============== Mock Provider ==============


class MockGitHubProvider:
    """Mock provider returning realistic fake GitHub data for MVP."""

    async def get_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        return [
            {
                "number": 42,
                "title": "feat: add user authentication flow",
                "state": "open",
                "user": {"login": "alice"},
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "merged_at": None,
                "head": {"ref": "feature/auth"},
                "base": {"ref": "main"},
                "additions": 320,
                "deletions": 45,
                "changed_files": 12,
                "labels": [{"name": "enhancement"}],
                "mergeable_state": "clean",
            },
            {
                "number": 41,
                "title": "fix: resolve merge conflict in config",
                "state": "open",
                "user": {"login": "bob"},
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "merged_at": None,
                "head": {"ref": "fix/config-conflict"},
                "base": {"ref": "main"},
                "additions": 10,
                "deletions": 5,
                "changed_files": 2,
                "labels": [{"name": "bug"}],
                "mergeable_state": "dirty",  # Has merge conflicts
            },
        ]

    async def get_recent_commits(
        self, owner: str, repo: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        return [
            {
                "sha": "abc1234567890def",
                "commit": {
                    "message": "feat: add login endpoint",
                    "author": {"name": "alice", "date": now.isoformat()},
                },
                "files": [{"filename": "src/auth.py"}, {"filename": "tests/test_auth.py"}],
            },
            {
                "sha": "def0987654321abc",
                "commit": {
                    "message": "chore: update dependencies",
                    "author": {"name": "bob", "date": now.isoformat()},
                },
                "files": [{"filename": "pyproject.toml"}],
            },
        ]

    async def get_ci_status(self, owner: str, repo: str) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        return [
            {
                "name": "pytest",
                "status": "completed",
                "conclusion": "success",
                "started_at": now.isoformat(),
                "completed_at": now.isoformat(),
                "pr_number": 42,
            },
            {
                "name": "lint",
                "status": "completed",
                "conclusion": "failure",
                "started_at": now.isoformat(),
                "completed_at": now.isoformat(),
                "pr_number": 41,
            },
        ]


# ============== Real Provider ==============


class HttpxGitHubProvider:
    """Provider that fetches real data from the GitHub REST API."""

    def __init__(self, token: str, api_base_url: str = "https://api.github.com"):
        self._base = api_base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request and handle errors."""
        resp = await self._client.get(f"{self._base}{path}", params=params)
        if resp.status_code == 401:
            raise ValueError("GitHub authentication failed — check GITHUB_TOKEN")
        if resp.status_code == 403:
            if "rate limit" in resp.text.lower():
                retry_after = resp.headers.get("Retry-After", "unknown")
                raise ValueError(f"GitHub API rate limit exceeded. Retry after: {retry_after}s")
            raise ValueError("GitHub API forbidden — check token permissions")
        if resp.status_code == 404:
            raise ValueError(f"GitHub resource not found: {path}")
        if resp.status_code >= 400:
            logger.warning("GitHub API error %s for %s: %s", resp.status_code, path, resp.text[:200])
            raise ValueError(f"GitHub API error: {resp.status_code}")
        return resp.json()

    async def get_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        pr_list = await self._get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": "open", "per_page": 30},
        )

        # Fetch individual PRs concurrently for additions/deletions/mergeable_state
        async def _fetch_detail(pr_summary: dict) -> dict[str, Any]:
            try:
                return await self._get(
                    f"/repos/{owner}/{repo}/pulls/{pr_summary['number']}"
                )
            except Exception as e:
                logger.warning("Failed to fetch PR #%s detail: %s", pr_summary.get("number"), e)
                return pr_summary  # Fall back to summary data

        return list(await asyncio.gather(*[_fetch_detail(pr) for pr in pr_list]))

    async def get_recent_commits(
        self, owner: str, repo: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        return await self._get(
            f"/repos/{owner}/{repo}/commits",
            params={"per_page": limit},
        )

    async def get_ci_status(self, owner: str, repo: str) -> list[dict[str, Any]]:
        data = await self._get(
            f"/repos/{owner}/{repo}/actions/runs",
            params={"per_page": 20},
        )
        runs = data.get("workflow_runs", [])
        result = []
        for run in runs:
            pr_numbers = run.get("pull_requests", [])
            pr_number = pr_numbers[0]["number"] if pr_numbers else None
            result.append({
                "name": run.get("name", "unknown"),
                "status": run.get("status", "unknown"),
                "conclusion": run.get("conclusion"),
                "started_at": run.get("run_started_at"),
                "completed_at": run.get("updated_at"),
                "pr_number": pr_number,
            })
        return result


# ============== Normalizer ==============


def normalize_pull_request(raw: dict[str, Any]) -> GitHubPullRequest:
    """Normalize raw GitHub API PR data into our schema."""
    return GitHubPullRequest(
        number=raw["number"],
        title=raw["title"],
        state=raw["state"],
        author=raw.get("user", {}).get("login", "unknown"),
        created_at=raw["created_at"],
        updated_at=raw["updated_at"],
        merged_at=raw.get("merged_at"),
        head_branch=raw.get("head", {}).get("ref", "unknown"),
        base_branch=raw.get("base", {}).get("ref", "main"),
        additions=raw.get("additions", 0),
        deletions=raw.get("deletions", 0),
        changed_files=raw.get("changed_files", 0),
        labels=[l["name"] for l in raw.get("labels", [])],
        has_conflicts=raw.get("mergeable_state") == "dirty",
    )


def normalize_commit(raw: dict[str, Any]) -> GitHubCommit:
    """Normalize raw GitHub API commit data into our schema."""
    commit_data = raw.get("commit", {})
    author_data = commit_data.get("author", {})
    return GitHubCommit(
        sha=raw["sha"],
        message=commit_data.get("message", ""),
        author=author_data.get("name", "unknown"),
        authored_at=author_data.get("date", datetime.now(timezone.utc).isoformat()),
        files_changed=len(raw.get("files", [])),
    )


def normalize_ci_status(raw: dict[str, Any]) -> GitHubCIStatus:
    """Normalize raw GitHub API CI check data into our schema."""
    return GitHubCIStatus(
        name=raw["name"],
        status=raw.get("status", "unknown"),
        conclusion=raw.get("conclusion"),
        started_at=raw.get("started_at"),
        completed_at=raw.get("completed_at"),
        pr_number=raw.get("pr_number"),
    )


# ============== Service ==============


def _parse_repo(github_repo: str) -> tuple[str, str]:
    """Parse 'owner/repo' from a github_repo string (URL or slug)."""
    # Handle full URLs like https://github.com/owner/repo
    repo = github_repo.rstrip("/")
    if "github.com" in repo:
        parts = repo.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    # Handle owner/repo format
    parts = repo.split("/")
    if len(parts) == 2:
        return parts[0], parts[1]
    raise ValueError(f"Cannot parse GitHub repo from: {github_repo}")


class GitHubService:
    """Orchestrates GitHub data sync: fetch, normalize, store, create risk signals."""

    def __init__(self, provider: GitHubDataProvider | None = None):
        self._provider = provider or MockGitHubProvider()

    async def sync_project(self, project_id: str, db: AsyncSession) -> dict[str, Any]:
        """Sync GitHub data for a project. Returns summary stats."""
        # Load project
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        if not project.github_repo:
            raise ValueError(f"Project {project_id} has no github_repo configured")

        owner, repo = _parse_repo(project.github_repo)

        # Fetch raw data from provider
        raw_prs = await self._provider.get_pull_requests(owner, repo)
        raw_commits = await self._provider.get_recent_commits(owner, repo)
        raw_ci = await self._provider.get_ci_status(owner, repo)

        # Normalize
        prs = [normalize_pull_request(r) for r in raw_prs]
        commits = [normalize_commit(r) for r in raw_commits]
        ci_checks = [normalize_ci_status(r) for r in raw_ci]

        now = datetime.now(timezone.utc)

        # Upsert GitHubContext
        ctx_result = await db.execute(
            select(GitHubContext).where(GitHubContext.project_id == project_id)
        )
        ctx = ctx_result.scalar_one_or_none()
        if not ctx:
            ctx = GitHubContext(
                id=str(uuid4()),
                project_id=project_id,
            )
            db.add(ctx)

        ctx.pull_requests = [pr.model_dump(mode="json") for pr in prs]
        ctx.recent_commits = [c.model_dump(mode="json") for c in commits]
        ctx.ci_status = [ci.model_dump(mode="json") for ci in ci_checks]
        ctx.last_synced_at = now
        ctx.sync_error = None

        # Auto-create risk signals (deduplicated — skip if matching open signal exists)
        risks_created = 0

        # Merge conflicts → HIGH severity
        for pr in prs:
            if pr.has_conflicts:
                title = f"Merge conflict in PR #{pr.number}: {pr.title}"
                existing = await db.execute(
                    select(RiskSignal).where(
                        RiskSignal.project_id == project_id,
                        RiskSignal.source == RiskSource.MERGE_CONFLICT.value,
                        RiskSignal.title == title,
                        RiskSignal.is_resolved == False,  # noqa: E712
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                risk = RiskSignal(
                    id=str(uuid4()),
                    project_id=project_id,
                    source=RiskSource.MERGE_CONFLICT.value,
                    severity=RiskSeverity.HIGH.value,
                    title=title,
                    description=f"PR #{pr.number} ({pr.head_branch} -> {pr.base_branch}) has merge conflicts that need resolution.",
                    recommended_action="Resolve merge conflicts and update the PR.",
                )
                db.add(risk)
                risks_created += 1

        # CI failures → MEDIUM severity
        for ci in ci_checks:
            if ci.conclusion == "failure":
                title = f"CI check '{ci.name}' failed"
                existing = await db.execute(
                    select(RiskSignal).where(
                        RiskSignal.project_id == project_id,
                        RiskSignal.source == RiskSource.CI_FAILURE.value,
                        RiskSignal.title == title,
                        RiskSignal.is_resolved == False,  # noqa: E712
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                risk = RiskSignal(
                    id=str(uuid4()),
                    project_id=project_id,
                    source=RiskSource.CI_FAILURE.value,
                    severity=RiskSeverity.MEDIUM.value,
                    title=title,
                    description=f"CI check '{ci.name}' failed{f' on PR #{ci.pr_number}' if ci.pr_number else ''}.",
                    recommended_action=f"Investigate and fix the failing '{ci.name}' check.",
                )
                db.add(risk)
                risks_created += 1

        await db.commit()
        await db.refresh(ctx)

        return {
            "project_id": project_id,
            "pull_requests_count": len(prs),
            "commits_count": len(commits),
            "ci_checks_count": len(ci_checks),
            "risks_created": risks_created,
            "last_synced_at": now,
        }

    async def get_context(self, project_id: str, db: AsyncSession) -> GitHubContext | None:
        """Get cached GitHub context for a project."""
        result = await db.execute(
            select(GitHubContext).where(GitHubContext.project_id == project_id)
        )
        return result.scalar_one_or_none()
