"""SharedContextService — reads/writes docs/shared_context/*.md and enriches with DB data."""

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import (
    GitHubContext,
    Plan,
    Project,
    RiskSignal,
    Subtask,
    Task,
    TeamMember,
)

# Resolve shared context dir relative to the repo root (two levels up from backend/src/)
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_SHARED_CONTEXT_DIR = _BACKEND_DIR.parent / "docs" / "shared_context"


class SharedContextService:
    """Reads shared-context markdown files and enriches them with live DB data."""

    def __init__(self, context_dir: Path | None = None):
        self._dir = context_dir or _SHARED_CONTEXT_DIR

    # ---- low-level helpers ----

    def _read_file(self, filename: str) -> str:
        """Read a shared-context markdown file. Returns empty string if missing."""
        path = self._dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _write_file(self, filename: str, content: str) -> None:
        """Write content to a shared-context markdown file."""
        path = self._dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # ---- public API ----

    async def gather_context(self, project_id: str, db: AsyncSession) -> dict[str, Any]:
        """Gather full shared context for the orchestrator.

        Combines:
        - Static markdown files from docs/shared_context/
        - Live DB data (team members, tasks, GitHub context, risks)

        Returns a dict keyed by section name.
        """
        # Static markdown files
        static_files = {
            "project_overview": self._read_file("PROJECT_OVERVIEW.md"),
            "team_members": self._read_file("TEAM_MEMBERS.md"),
            "hosted_agents": self._read_file("HOSTED_AGENTS.md"),
            "project_plan": self._read_file("PROJECT_PLAN.md"),
            "task_graph": self._read_file("TASK_GRAPH.md"),
            "integrations_github": self._read_file("INTEGRATIONS_GITHUB.md"),
        }

        # Live DB enrichment
        project = await self._get_project(project_id, db)
        members = await self._get_team_members(project_id, db)
        tasks = await self._get_tasks(project_id, db)
        github_ctx = await self._get_github_context(project_id, db)
        risks = await self._get_open_risks(project_id, db)

        return {
            **static_files,
            "project": self._serialize_project(project) if project else {},
            "team_members_db": [self._serialize_member(m) for m in members],
            "tasks_db": [self._serialize_task(t) for t in tasks],
            "github_context": self._serialize_github(github_ctx) if github_ctx else {},
            "open_risks": [self._serialize_risk(r) for r in risks],
        }

    async def update_context_file(self, filename: str, content: str) -> None:
        """Update a specific shared-context file (e.g. after reviewer enrichment)."""
        self._write_file(filename, content)

    # ---- DB queries ----

    async def _get_project(self, project_id: str, db: AsyncSession) -> Project | None:
        result = await db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def _get_team_members(self, project_id: str, db: AsyncSession) -> list[TeamMember]:
        result = await db.execute(
            select(TeamMember).where(TeamMember.project_id == project_id)
        )
        return list(result.scalars().all())

    async def _get_tasks(self, project_id: str, db: AsyncSession) -> list[Task]:
        """Get tasks linked to this project via plans."""
        plan_result = await db.execute(
            select(Plan.task_id).where(Plan.project_id == project_id)
        )
        task_ids = [row[0] for row in plan_result.all()]
        if not task_ids:
            return []
        result = await db.execute(select(Task).where(Task.id.in_(task_ids)))
        return list(result.scalars().all())

    async def _get_github_context(
        self, project_id: str, db: AsyncSession
    ) -> GitHubContext | None:
        result = await db.execute(
            select(GitHubContext).where(GitHubContext.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def _get_open_risks(self, project_id: str, db: AsyncSession) -> list[RiskSignal]:
        result = await db.execute(
            select(RiskSignal).where(
                RiskSignal.project_id == project_id,
                RiskSignal.is_resolved == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    # ---- serializers ----

    @staticmethod
    def _serialize_project(p: Project) -> dict[str, Any]:
        return {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "goals": p.goals,
            "milestones": p.milestones,
            "github_repo": p.github_repo,
        }

    @staticmethod
    def _serialize_member(m: TeamMember) -> dict[str, Any]:
        return {
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role,
            "skills": m.skills,
            "capacity": m.capacity,
            "current_load": m.current_load,
        }

    @staticmethod
    def _serialize_task(t: Task) -> dict[str, Any]:
        return {
            "id": t.id,
            "title": t.title,
            "task_type": t.task_type,
            "status": t.status.value if hasattr(t.status, "value") else t.status,
            "assigned_agent_id": t.assigned_agent_id,
        }

    @staticmethod
    def _serialize_github(g: GitHubContext) -> dict[str, Any]:
        return {
            "pull_requests": g.pull_requests,
            "recent_commits": g.recent_commits,
            "ci_status": g.ci_status,
            "last_synced_at": g.last_synced_at.isoformat() if g.last_synced_at else None,
        }

    @staticmethod
    def _serialize_risk(r: RiskSignal) -> dict[str, Any]:
        return {
            "id": r.id,
            "source": r.source,
            "severity": r.severity,
            "title": r.title,
            "description": r.description,
        }
