"""SharedContextService — reads/writes docs/shared_context/*.md and enriches with DB data."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import (
    Agent,
    GitHubContext,
    Plan,
    Project,
    RiskSignal,
    Subtask,
    Task,
    TeamMember,
)

logger = logging.getLogger(__name__)

# Resolve shared context dir relative to the repo root (two levels up from backend/src/)
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def _resolve_shared_context_dir() -> Path:
    """Resolve context dir for both local monorepo and deployed subtree layouts."""
    explicit = os.getenv("SHARED_CONTEXT_DIR")
    if explicit:
        return Path(explicit)

    candidates = [
        # Local monorepo run from backend/: <repo>/docs/shared_context
        _BACKEND_DIR.parent / "docs" / "shared_context",
        # Dokku subtree deployment: /app/docs/shared_context
        _BACKEND_DIR / "docs" / "shared_context",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    # Fall back to deployed layout; write path is created on demand.
    return candidates[1]


_SHARED_CONTEXT_DIR = _resolve_shared_context_dir()


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

    async def refresh_context_files(self, project_id: str, db: AsyncSession) -> dict[str, bool]:
        """Re-render all shared context MD files from current DB state.

        Called automatically after GitHub sync and available for manual trigger.
        Returns a dict of {filename: was_updated}.
        """
        project = await self._get_project(project_id, db)
        if not project:
            logger.warning("refresh_context_files: project %s not found", project_id)
            return {}

        results: dict[str, bool] = {}

        # 1. PROJECT_OVERVIEW.md
        content = self._render_project_overview(project)
        self._write_file("PROJECT_OVERVIEW.md", content)
        results["PROJECT_OVERVIEW.md"] = True

        # 2. INTEGRATIONS_GITHUB.md
        github_ctx = await self._get_github_context(project_id, db)
        content = self._render_github_integration(project, github_ctx)
        self._write_file("INTEGRATIONS_GITHUB.md", content)
        results["INTEGRATIONS_GITHUB.md"] = True

        # 3. TASK_GRAPH.md
        tasks = await self._get_tasks(project_id, db)
        risks = await self._get_open_risks(project_id, db)
        content = self._render_task_graph(tasks, risks)
        self._write_file("TASK_GRAPH.md", content)
        results["TASK_GRAPH.md"] = True

        # 4. TEAM_MEMBERS.md
        members = await self._get_team_members(project_id, db)
        content = self._render_team_members(members)
        self._write_file("TEAM_MEMBERS.md", content)
        results["TEAM_MEMBERS.md"] = True

        # 5. HOSTED_AGENTS.md
        agents = await self._get_project_agents(project_id, db)
        content = self._render_hosted_agents(agents)
        self._write_file("HOSTED_AGENTS.md", content)
        results["HOSTED_AGENTS.md"] = True

        logger.info("Refreshed %d shared context files for project %s", len(results), project_id)
        return results

    # ---- renderers (DB data -> markdown) ----

    @staticmethod
    def _render_project_overview(p: Project) -> str:
        goals = p.goals or []
        milestones = p.milestones or []
        goals_md = "\n".join(f"- {g}" for g in goals) if goals else "_No goals defined._"
        milestones_md = "\n".join(f"- {m}" for m in milestones) if milestones else "_No milestones defined._"
        return (
            f"# Project Overview\n\n"
            f"## Project Name\n{p.name}\n\n"
            f"## Description\n{p.description or '_No description._'}\n\n"
            f"## Goals\n{goals_md}\n\n"
            f"## Milestones\n{milestones_md}\n\n"
            f"## Repository\n{p.github_repo or '_Not configured._'}\n"
        )

    @staticmethod
    def _render_github_integration(p: Project, ctx: GitHubContext | None) -> str:
        repo = p.github_repo or "_Not configured_"
        if not ctx:
            return (
                f"# GitHub Integration Context\n\n"
                f"## Repository\n{repo}\n\n"
                f"_No GitHub data synced yet. Run sync-github to populate._\n"
            )

        synced = ctx.last_synced_at.strftime("%Y-%m-%d %H:%M UTC") if ctx.last_synced_at else "never"

        # PRs
        prs = ctx.pull_requests or []
        if prs:
            pr_lines = []
            for pr in prs:
                conflict = " **[CONFLICT]**" if pr.get("has_conflicts") else ""
                labels = ", ".join(pr.get("labels", []))
                label_str = f" [{labels}]" if labels else ""
                pr_lines.append(
                    f"- **#{pr['number']}** {pr['title']} "
                    f"(`{pr.get('head_branch', '?')}` -> `{pr.get('base_branch', 'main')}`) "
                    f"by {pr.get('author', '?')} "
                    f"— +{pr.get('additions', 0)}/-{pr.get('deletions', 0)}, "
                    f"{pr.get('changed_files', 0)} files{label_str}{conflict}"
                )
            pr_md = "\n".join(pr_lines)
        else:
            pr_md = "_No open pull requests._"

        # Commits
        commits = ctx.recent_commits or []
        if commits:
            commit_lines = []
            for c in commits[:10]:  # cap at 10
                sha_short = c.get("sha", "")[:7]
                msg = c.get("message", "").split("\n")[0][:80]
                commit_lines.append(f"- `{sha_short}` {msg} — {c.get('author', '?')}")
            commit_md = "\n".join(commit_lines)
        else:
            commit_md = "_No recent commits._"

        # CI
        ci_checks = ctx.ci_status or []
        if ci_checks:
            ci_lines = []
            for ci in ci_checks:
                conclusion = ci.get("conclusion") or ci.get("status", "unknown")
                icon = {"success": "pass", "failure": "FAIL", "pending": "pending"}.get(conclusion, conclusion)
                pr_ref = f" (PR #{ci['pr_number']})" if ci.get("pr_number") else ""
                ci_name = ci.get("name") or ci.get("workflow", "check")
                ci_lines.append(f"- **{ci_name}**: {icon}{pr_ref}")
            ci_md = "\n".join(ci_lines)
        else:
            ci_md = "_No CI checks recorded._"

        # Merge constraints
        conflicts = [pr for pr in prs if pr.get("has_conflicts")]
        failures = [ci for ci in ci_checks if ci.get("conclusion") == "failure"]
        constraints = []
        if conflicts:
            constraints.append(f"- {len(conflicts)} PR(s) have merge conflicts")
        if failures:
            constraints.append(f"- {len(failures)} CI check(s) failing")
        constraints_md = "\n".join(constraints) if constraints else "_No blocking constraints._"

        return (
            f"# GitHub Integration Context\n\n"
            f"## Repository\n{repo}\n\n"
            f"**Last synced:** {synced}\n\n"
            f"## PR Status Snapshot\n{pr_md}\n\n"
            f"## Recent Commits\n{commit_md}\n\n"
            f"## CI Status Snapshot\n{ci_md}\n\n"
            f"## Merge Constraints\n{constraints_md}\n"
        )

    @staticmethod
    def _render_task_graph(tasks: list[Task], risks: list[RiskSignal]) -> str:
        if tasks:
            task_lines = []
            for t in tasks:
                status = t.status.value if hasattr(t.status, "value") else t.status
                agent = f" (agent: {t.assigned_agent_id})" if t.assigned_agent_id else ""
                task_lines.append(f"- **{t.title}** [{status}]{agent}")
            tasks_md = "\n".join(task_lines)
        else:
            tasks_md = "_No tasks linked to this project._"

        if risks:
            risk_lines = []
            for r in risks:
                risk_lines.append(f"- [{r.severity}] {r.title}")
            risks_md = "\n".join(risk_lines)
        else:
            risks_md = "_No open risks._"

        return (
            f"# Task Graph\n\n"
            f"## Active Tasks\n{tasks_md}\n\n"
            f"## Open Risks\n{risks_md}\n"
        )

    @staticmethod
    def _render_team_members(members: list[TeamMember]) -> str:
        if members:
            lines = []
            for m in members:
                skills = ", ".join(m.skills) if m.skills else "none"
                load = f"{m.current_load}/{m.capacity}" if m.capacity else str(m.current_load or 0)
                member_id = m.user_id[:8] if m.user_id else "?"
                lines.append(f"- **{m.role}** (id:{member_id}) — skills: {skills}, load: {load}")
            members_md = "\n".join(lines)
        else:
            members_md = "_No team members assigned._"
        return f"# Team Members\n\n{members_md}\n"

    @staticmethod
    def _render_hosted_agents(agents: list[Agent]) -> str:
        if agents:
            lines = []
            for a in agents:
                status = a.status.value if hasattr(a.status, "value") else a.status
                skills = ", ".join(a.skills) if a.skills else "none"
                lines.append(f"- **{a.name}** [{status}] — skills: {skills}, provider: {a.inference_provider or '?'}")
            agents_md = "\n".join(lines)
        else:
            agents_md = "_No hosted agents available._"
        return f"# Hosted Agents\n\n{agents_md}\n"

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

    async def _get_project_agents(self, project_id: str, db: AsyncSession) -> list[Agent]:
        """Get agents available to this project (all online agents for now).

        TODO: Filter by ProjectAllowedAgent for per-project scoping.
        """
        from src.core.state import AgentStatus

        result = await db.execute(
            select(Agent).where(Agent.status == AgentStatus.ONLINE)
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
