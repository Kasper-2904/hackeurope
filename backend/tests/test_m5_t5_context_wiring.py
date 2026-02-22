"""Tests for M5-T5: Wire callers to pass project_id + context write-back."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.plans import generate_plan
from src.api.schemas import PlanGenerate
from src.api.subtasks import _run_subtask_orchestration
from src.core.orchestrator import aggregate_results, OrchestratorState
from src.core.state import PlanStatus, TaskStatus
from src.storage.models import Plan, Project, Task, User


# ============== Helpers ==============


async def _make_user(db: AsyncSession) -> User:
    user = User(
        id=str(uuid4()),
        email=f"test-{uuid4().hex[:6]}@example.com",
        username=f"testuser-{uuid4().hex[:6]}",
        hashed_password="fakehash",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_project(db: AsyncSession, owner: User) -> Project:
    project = Project(
        id=str(uuid4()),
        name="Test Project",
        owner_id=owner.id,
    )
    db.add(project)
    await db.flush()
    return project


async def _make_task(db: AsyncSession, owner: User) -> Task:
    task = Task(
        id=str(uuid4()),
        title="Test Task",
        description="Build the feature",
        task_type="code_generation",
        status=TaskStatus.IN_PROGRESS,
        created_by_id=owner.id,
    )
    db.add(task)
    await db.flush()
    return task


# ============== plans.py: generate_plan calls execute_task + persists Plan ==============


class TestGeneratePlan:
    """Test that generate_plan calls orchestrator.execute_task and creates a Plan row."""

    @pytest.mark.asyncio
    async def test_generate_plan_creates_plan_row(self, db_session: AsyncSession):
        """generate_plan should call execute_task and persist a Plan."""
        user = await _make_user(db_session)
        project = await _make_project(db_session, user)
        task = await _make_task(db_session, user)
        await db_session.commit()

        mock_result = {
            "task_id": task.id,
            "status": "completed",
            "result": "Step 1: generate code\nStep 2: review code",
            "plan": [
                {"skill": "generate_code", "status": "completed"},
                {"skill": "review_code", "status": "completed"},
            ],
            "error": None,
        }

        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_task = AsyncMock(return_value=mock_result)

        mock_paid = MagicMock()
        mock_paid.check_usage_limit = AsyncMock(return_value=True)
        mock_paid.track_usage = AsyncMock()

        with (
            patch("src.core.orchestrator.get_orchestrator", return_value=mock_orchestrator),
            patch("src.api.plans.get_paid_service", return_value=mock_paid),
        ):
            result = await generate_plan(
                plan_data=PlanGenerate(task_id=task.id, project_id=project.id),
                current_user=user,
                db=db_session,
            )

        # Verify orchestrator was called with project_id
        mock_orchestrator.execute_task.assert_called_once()
        call_kwargs = mock_orchestrator.execute_task.call_args.kwargs
        assert call_kwargs["project_id"] == project.id
        assert call_kwargs["task_type"] == "plan_generation"

        # Verify a Plan row was persisted
        assert result["plan_id"] is not None
        plan_result = await db_session.execute(
            select(Plan).where(Plan.id == result["plan_id"])
        )
        plan = plan_result.scalar_one()
        assert plan.project_id == project.id
        assert plan.task_id == task.id
        assert plan.status == PlanStatus.PENDING_PM_APPROVAL.value
        assert "steps" in plan.plan_data

    @pytest.mark.asyncio
    async def test_generate_plan_returns_correct_response(self, db_session: AsyncSession):
        """generate_plan should return PlanGenerateResponse-compatible dict."""
        user = await _make_user(db_session)
        project = await _make_project(db_session, user)
        task = await _make_task(db_session, user)
        await db_session.commit()

        mock_result = {
            "task_id": task.id,
            "status": "completed",
            "result": "Generated plan",
            "plan": [{"skill": "generate_code", "status": "completed"}],
            "error": None,
        }

        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_task = AsyncMock(return_value=mock_result)

        mock_paid = MagicMock()
        mock_paid.check_usage_limit = AsyncMock(return_value=True)
        mock_paid.track_usage = AsyncMock()

        with (
            patch("src.core.orchestrator.get_orchestrator", return_value=mock_orchestrator),
            patch("src.api.plans.get_paid_service", return_value=mock_paid),
        ):
            result = await generate_plan(
                plan_data=PlanGenerate(task_id=task.id, project_id=project.id),
                current_user=user,
                db=db_session,
            )

        assert result["task_id"] == task.id
        assert result["status"] == "completed"
        assert result["plan_id"] is not None
        assert result["rationale"] == "Generated plan"
        assert result["error"] is None


# ============== subtasks.py: _run_subtask_orchestration passes project_id ==============


class TestSubtaskOrchestration:
    """Test that subtask dispatch passes project_id to orchestrator."""

    @pytest.mark.asyncio
    async def test_run_subtask_orchestration_passes_project_id(self):
        """_run_subtask_orchestration should forward project_id to execute_task."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_task = AsyncMock(return_value={"status": "completed"})

        project_id = str(uuid4())

        with patch("src.api.subtasks.get_orchestrator", return_value=mock_orchestrator):
            await _run_subtask_orchestration(
                subtask_id="sub-1",
                task_id="task-1",
                title="Build component",
                description="Build the React component",
                current_user_id="user-1",
                project_id=project_id,
            )

        mock_orchestrator.execute_task.assert_called_once()
        call_kwargs = mock_orchestrator.execute_task.call_args.kwargs
        assert call_kwargs["project_id"] == project_id
        assert call_kwargs["subtask_id"] == "sub-1"
        assert call_kwargs["task_type"] == "subtask_execution"

    @pytest.mark.asyncio
    async def test_run_subtask_orchestration_without_project_id(self):
        """_run_subtask_orchestration should work with project_id=None."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_task = AsyncMock(return_value={"status": "completed"})

        with patch("src.api.subtasks.get_orchestrator", return_value=mock_orchestrator):
            await _run_subtask_orchestration(
                subtask_id="sub-1",
                task_id="task-1",
                title="Build component",
                description="Build the React component",
                current_user_id="user-1",
            )

        call_kwargs = mock_orchestrator.execute_task.call_args.kwargs
        assert call_kwargs["project_id"] is None


# ============== orchestrator: aggregate_results writes back context ==============


class TestAggregateResultsContextWriteback:
    """Test that aggregate_results refreshes shared context files."""

    @pytest.mark.asyncio
    async def test_aggregate_refreshes_context_when_project_id_set(self):
        """aggregate_results should call refresh_context_files when project_id is present."""
        project_id = str(uuid4())
        state: OrchestratorState = {
            "task_id": "task-1",
            "task_type": "code_generation",
            "task_description": "Build feature",
            "input_data": {},
            "plan": [{"skill": "generate_code", "status": "completed", "result": "done"}],
            "current_step": 1,
            "selected_agent_id": None,
            "skill_name": None,
            "skill_inputs": {},
            "step_results": [
                {"step": 1, "agent_id": "a1", "skill": "generate_code", "result": "code here"}
            ],
            "final_result": None,
            "error": None,
            "status": "executing",
            "user_id": None,
            "team_id": None,
            "subtask_id": None,
            "project_id": project_id,
            "shared_context": "",
        }

        mock_ctx_service = MagicMock()
        mock_ctx_service.refresh_context_files = AsyncMock(return_value={"file1": True})

        mock_session = AsyncMock()

        with (
            patch(
                "src.core.orchestrator.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "src.services.context_service.SharedContextService",
                return_value=mock_ctx_service,
            ) as mock_cls,
        ):
            # Make the context manager work
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            result = await aggregate_results(state)

        assert result["status"] == "completed"
        mock_ctx_service.refresh_context_files.assert_called_once_with(
            project_id, mock_session
        )

    @pytest.mark.asyncio
    async def test_aggregate_skips_writeback_without_project_id(self):
        """aggregate_results should skip context refresh when project_id is None."""
        state: OrchestratorState = {
            "task_id": "task-1",
            "task_type": "code_generation",
            "task_description": "Build feature",
            "input_data": {},
            "plan": [],
            "current_step": 0,
            "selected_agent_id": None,
            "skill_name": None,
            "skill_inputs": {},
            "step_results": [],
            "final_result": None,
            "error": None,
            "status": "executing",
            "user_id": None,
            "team_id": None,
            "subtask_id": None,
            "project_id": None,
            "shared_context": None,
        }

        with patch(
            "src.services.context_service.SharedContextService",
        ) as mock_cls:
            result = await aggregate_results(state)

        # SharedContextService should never be instantiated
        mock_cls.assert_not_called()
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_aggregate_handles_writeback_failure_gracefully(self):
        """aggregate_results should not crash if context refresh fails."""
        project_id = str(uuid4())
        state: OrchestratorState = {
            "task_id": "task-1",
            "task_type": "code_generation",
            "task_description": "Build feature",
            "input_data": {},
            "plan": [],
            "current_step": 0,
            "selected_agent_id": None,
            "skill_name": None,
            "skill_inputs": {},
            "step_results": [],
            "final_result": None,
            "error": None,
            "status": "executing",
            "user_id": None,
            "team_id": None,
            "subtask_id": None,
            "project_id": project_id,
            "shared_context": None,
        }

        mock_ctx_service = MagicMock()
        mock_ctx_service.refresh_context_files = AsyncMock(
            side_effect=Exception("DB connection failed")
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "src.core.orchestrator.async_session_factory",
                return_value=mock_session,
            ),
            patch(
                "src.services.context_service.SharedContextService",
                return_value=mock_ctx_service,
            ),
        ):
            result = await aggregate_results(state)

        # Should still complete successfully despite write-back failure
        assert result["status"] == "completed"
        assert result["final_result"] == "No results generated."
