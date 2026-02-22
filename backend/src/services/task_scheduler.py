"""
Background task scheduler for automatically picking up pending tasks
and assigning them to agents via the orchestrator.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.orchestrator import get_orchestrator
from src.core.state import PlanStatus, TaskStatus
from src.storage.database import AsyncSessionLocal as async_session_factory
from src.storage.models import Plan, Subtask, Task

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Background scheduler that periodically checks for pending tasks
    and dispatches them to the orchestrator.
    """

    def __init__(self, poll_interval: int = 30):
        """
        Initialize the task scheduler.

        Args:
            poll_interval: How often to check for pending tasks (seconds)
        """
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the background scheduler."""
        if self._running:
            logger.warning("Task scheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Task scheduler started with {self.poll_interval}s poll interval")

    async def stop(self):
        """Stop the background scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Task scheduler stopped")

    async def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                await self._process_pending_tasks()
            except Exception as e:
                logger.error(f"Error in task scheduler: {e}", exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def _process_pending_tasks(self):
        """
        Find pending/assigned/in_progress tasks with approved plans and dispatch them to the orchestrator.
        """
        logger.debug("Checking for pending tasks...")
        async with async_session_factory() as session:
            # Find tasks that are PENDING, ASSIGNED, or IN_PROGRESS and have an approved plan
            approved_plan_task_ids = select(Plan.task_id).where(
                Plan.status == PlanStatus.APPROVED.value
            )

            result = await session.execute(
                select(Task)
                .where(
                    Task.status.in_(
                        [TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
                    ),
                    Task.id.in_(approved_plan_task_ids),
                )
                .limit(10)  # Process in batches
            )
            pending_tasks = list(result.scalars().all())

            logger.info(
                f"Found {len(pending_tasks)} pending/assigned/in_progress tasks with approved plans"
            )

            if not pending_tasks:
                return

            for task in pending_tasks:
                await self._dispatch_task(session, task)

    async def _dispatch_task(self, session: AsyncSession, task: Task):
        """
        Dispatch a single task to the orchestrator.
        """
        try:
            # Get the approved plan to find the project_id
            plan_result = await session.execute(
                select(Plan).where(
                    Plan.task_id == task.id,
                    Plan.status == PlanStatus.APPROVED.value,
                )
            )
            plan = plan_result.scalar_one_or_none()

            if not plan:
                logger.warning(f"No approved plan found for task {task.id}")
                return

            # Update task status to IN_PROGRESS
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.utcnow()
            await session.commit()

            logger.info(f"Dispatching task {task.id} to orchestrator")

            # Execute through orchestrator
            orchestrator = get_orchestrator()
            result = await orchestrator.execute_task(
                task_id=task.id,
                task_type=task.task_type,
                description=task.description or task.title,
                input_data=task.input_data,
                team_id=task.team_id,
                user_id=task.created_by_id,
                project_id=plan.project_id,
            )

            # Update task based on result
            if result.get("status") == "completed":
                task.status = TaskStatus.COMPLETED
                task.progress = 1.0
                task.result = result

                draft_text = result.get("result") or ""
                if not draft_text:
                    steps = result.get("steps") or []
                    parts = []
                    for i, s in enumerate(steps, 1):
                        skill = s.get("skill", "step")
                        res = s.get("result", "")
                        if res:
                            parts.append(f"## Step {i}: {skill}\n{res}")
                    draft_text = "\n\n".join(parts)
                if not draft_text:
                    draft_text = "Orchestration completed (no text output)."

                draft_payload = {
                    "output": draft_text,
                    "type": "orchestrator_output",
                }

                sub_result = await session.execute(
                    select(Subtask)
                    .where(Subtask.task_id == task.id)
                    .order_by(Subtask.created_at)
                    .limit(1)
                )
                first_subtask = sub_result.scalar_one_or_none()
                if first_subtask:
                    first_subtask.draft_content = draft_payload
                    first_subtask.status = "draft_generated"
                    first_subtask.draft_generated_at = datetime.utcnow()
                else:
                    from uuid import uuid4

                    new_subtask = Subtask(
                        id=str(uuid4()),
                        task_id=task.id,
                        title="Orchestrator Output",
                        description="Auto-generated from orchestrator execution",
                        priority=1,
                        status="draft_generated",
                        draft_content=draft_payload,
                        draft_generated_at=datetime.utcnow(),
                    )
                    session.add(new_subtask)
            else:
                task.status = TaskStatus.FAILED
                task.error = result.get("error")

            task.completed_at = datetime.utcnow()
            await session.commit()

            logger.info(f"Task {task.id} completed with status: {result.get('status')}")

        except Exception as e:
            logger.error(f"Error dispatching task {task.id}: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            await session.commit()

    async def process_single_task(
        self,
        task_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        """
        Manually trigger processing of a single task.
        Used when PM approves a plan and wants immediate execution.

        Returns:
            Result from orchestrator execution
        """
        async with async_session_factory() as session:
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()

            if not task:
                return {"error": "Task not found", "status": "failed"}

            if task.status not in (TaskStatus.PENDING, TaskStatus.ASSIGNED):
                return {
                    "error": f"Task cannot be started from status {task.status.value}",
                    "status": "failed",
                }

            # Update status
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.utcnow()
            await session.commit()

            # Execute
            orchestrator = get_orchestrator()
            try:
                orchestration_result = await orchestrator.execute_task(
                    task_id=task.id,
                    task_type=task.task_type,
                    description=task.description or task.title,
                    input_data=task.input_data,
                    team_id=task.team_id,
                    user_id=task.created_by_id,
                    project_id=project_id,
                )

                if orchestration_result.get("status") == "completed":
                    task.status = TaskStatus.COMPLETED
                    task.progress = 1.0
                    task.result = orchestration_result

                    # Write result to a subtask's draft_content so the Draft tab shows it.
                    # Build draft from result text, falling back to step results.
                    draft_text = orchestration_result.get("result") or ""
                    if not draft_text:
                        # Fallback: concatenate step results
                        steps = orchestration_result.get("steps") or []
                        parts = []
                        for i, s in enumerate(steps, 1):
                            skill = s.get("skill", "step")
                            res = s.get("result", "")
                            if res:
                                parts.append(f"## Step {i}: {skill}\n{res}")
                        draft_text = "\n\n".join(parts)
                    if not draft_text:
                        draft_text = "Orchestration completed (no text output)."

                    draft_payload = {
                        "output": draft_text,
                        "type": "orchestrator_output",
                    }

                    sub_result = await session.execute(
                        select(Subtask)
                        .where(Subtask.task_id == task_id)
                        .order_by(Subtask.created_at)
                        .limit(1)
                    )
                    first_subtask = sub_result.scalar_one_or_none()
                    if first_subtask:
                        first_subtask.draft_content = draft_payload
                        first_subtask.status = "draft_generated"
                        first_subtask.draft_generated_at = datetime.utcnow()
                    else:
                        # No subtask exists — create one to hold the draft
                        from uuid import uuid4

                        new_subtask = Subtask(
                            id=str(uuid4()),
                            task_id=task_id,
                            title="Orchestrator Output",
                            description="Auto-generated from orchestrator execution",
                            priority=1,
                            status="draft_generated",
                            draft_content=draft_payload,
                            draft_generated_at=datetime.utcnow(),
                        )
                        session.add(new_subtask)
                else:
                    task.status = TaskStatus.FAILED
                    task.error = orchestration_result.get("error")

                task.completed_at = datetime.utcnow()
                await session.commit()

                return orchestration_result

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.utcnow()
                await session.commit()
                return {"error": str(e), "status": "failed"}


# Global scheduler instance
_scheduler: TaskScheduler | None = None


def get_task_scheduler() -> TaskScheduler:
    """Get the global task scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler
