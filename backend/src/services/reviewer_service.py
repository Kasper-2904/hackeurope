"""ReviewerService — Claude-powered final-gate reviewer for tasks."""

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.state import RiskSeverity, RiskSource
from src.services.context_service import SharedContextService
from src.services.llm_service import LLMService, get_llm_service
from src.storage.models import GitHubContext, Plan, RiskSignal, Subtask, Task


class ReviewerService:
    """Analyzes a completed task against shared context and GitHub data.

    Produces:
    - blocker / non-blocker findings as RiskSignal rows
    - merge-readiness decision
    - context enrichment notes
    """

    def __init__(self, llm: LLMService | None = None):
        self._llm = llm or get_llm_service()
        self._context = SharedContextService()

    async def finalize_task(
        self, task_id: str, project_id: str, db: AsyncSession
    ) -> dict[str, Any]:
        """Run the reviewer analysis on a task.

        Returns:
            Dict with findings, merge_ready flag, and summary.
        """
        # Gather context
        shared_ctx = await self._context.gather_context(project_id, db)

        # Get task + subtasks
        task = await self._get_task(task_id, db)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        subtasks = await self._get_subtasks(task_id, db)

        # Build prompt
        system_prompt = (
            "You are the Reviewer Agent for a software delivery platform. "
            "Analyze the completed task, its subtasks, and the project context.\n\n"
            "Check for:\n"
            "1. Consistency with other tasks and the project plan\n"
            "2. Potential merge conflicts with in-flight work\n"
            "3. CI/quality risks\n"
            "4. Missing test coverage or documentation\n"
            "5. Security concerns\n\n"
            "Respond in JSON:\n"
            "{\n"
            '  "merge_ready": true/false,\n'
            '  "findings": [\n'
            '    {"title": "...", "severity": "low|medium|high|critical", '
            '"is_blocker": false, "description": "...", "recommended_action": "..."}\n'
            "  ],\n"
            '  "summary": "...",\n'
            '  "context_updates": "Optional notes to add to shared context"\n'
            "}"
        )

        user_message = self._build_review_prompt(task, subtasks, shared_ctx)

        try:
            result = await self._llm.complete_json(
                system=system_prompt,
                user_message=user_message,
            )
        except Exception as e:
            return {
                "task_id": task_id,
                "merge_ready": False,
                "findings": [],
                "summary": f"Reviewer LLM call failed: {e}",
                "error": str(e),
            }

        # Persist findings as RiskSignals
        findings = result.get("findings", [])
        risks_created = 0
        for finding in findings:
            severity = finding.get("severity", "medium")
            risk = RiskSignal(
                id=str(uuid4()),
                project_id=project_id,
                task_id=task_id,
                source=RiskSource.REVIEWER.value,
                severity=severity,
                title=finding.get("title", "Reviewer finding"),
                description=finding.get("description"),
                rationale=finding.get("recommended_action"),
                recommended_action=finding.get("recommended_action"),
            )
            db.add(risk)
            risks_created += 1

        # Update shared context if reviewer has notes
        context_updates = result.get("context_updates")
        if context_updates:
            await self._context.update_context_file(
                "TEAM_CONTEXT.md",
                f"# Team Context\n\n## Latest Reviewer Notes\n{context_updates}\n",
            )

        await db.flush()

        return {
            "task_id": task_id,
            "merge_ready": result.get("merge_ready", False),
            "findings": findings,
            "risks_created": risks_created,
            "summary": result.get("summary", ""),
        }

    # ---- Helpers ----

    async def _get_task(self, task_id: str, db: AsyncSession) -> Task | None:
        result = await db.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def _get_subtasks(self, task_id: str, db: AsyncSession) -> list[Subtask]:
        result = await db.execute(
            select(Subtask).where(Subtask.task_id == task_id)
        )
        return list(result.scalars().all())

    def _build_review_prompt(
        self,
        task: Task,
        subtasks: list[Subtask],
        ctx: dict[str, Any],
    ) -> str:
        parts = [
            f"## Task Under Review\n**{task.title}**\n{task.description or 'No description'}",
            f"Type: {task.task_type} | Status: {task.status}",
        ]

        if subtasks:
            sub_lines = []
            for s in subtasks:
                sub_lines.append(
                    f"- [{s.status}] {s.title}"
                    + (f" (draft v{s.draft_version})" if s.draft_version else "")
                )
            parts.append(f"**Subtasks ({len(subtasks)}):**\n" + "\n".join(sub_lines))

        # GitHub context
        gh = ctx.get("github_context", {})
        if gh:
            prs = gh.get("pull_requests", [])
            ci = gh.get("ci_status", [])
            if prs:
                parts.append(f"**Open PRs:** {len(prs)}")
            failures = [c for c in ci if c.get("conclusion") == "failure"]
            if failures:
                names = [f["name"] for f in failures]
                parts.append(f"**CI Failures:** {', '.join(names)}")

        # Existing risks
        risks = ctx.get("open_risks", [])
        if risks:
            risk_lines = [f"- [{r['severity']}] {r['title']}" for r in risks]
            parts.append(f"**Existing Risks:**\n" + "\n".join(risk_lines))

        # Existing tasks for conflict detection
        tasks = ctx.get("tasks_db", [])
        if tasks:
            other_tasks = [t for t in tasks if t["id"] != task.id]
            if other_tasks:
                task_lines = [f"- [{t['status']}] {t['title']}" for t in other_tasks]
                parts.append(f"**Other In-Flight Tasks:**\n" + "\n".join(task_lines))

        return "\n\n".join(parts)


# Module-level singleton
_reviewer_service: ReviewerService | None = None


def get_reviewer_service() -> ReviewerService:
    """Get the global ReviewerService instance."""
    global _reviewer_service
    if _reviewer_service is None:
        _reviewer_service = ReviewerService()
    return _reviewer_service
