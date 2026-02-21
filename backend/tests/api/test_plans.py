"""Unit tests for plans API endpoints."""

import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import check_user_role_for_project, require_pm_role_for_project
from src.core.state import PlanStatus, UserRole
from src.storage.models import Plan, Project, TeamMember, User


class TestPMRoleVerification:
    """Tests for PM role verification logic."""

    @pytest.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        user = User(
            id=str(uuid4()),
            email="test@example.com",
            username="testuser",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest.fixture
    async def superuser(self, db_session: AsyncSession) -> User:
        """Create a superuser."""
        user = User(
            id=str(uuid4()),
            email="admin@example.com",
            username="adminuser",
            hashed_password="hashed",
            is_active=True,
            is_superuser=True,
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest.fixture
    async def test_project(self, db_session: AsyncSession, test_user: User) -> Project:
        """Create a test project."""
        project = Project(
            id=str(uuid4()),
            name="Test Project",
            owner_id=test_user.id,
        )
        db_session.add(project)
        await db_session.commit()
        return project

    async def test_check_user_role_returns_false_when_no_membership(
        self, db_session: AsyncSession, test_user: User, test_project: Project
    ):
        """User without team membership should return False."""
        result = await check_user_role_for_project(
            db_session, test_user.id, test_project.id, [UserRole.PM]
        )
        assert result is False

    async def test_check_user_role_returns_true_for_pm(
        self, db_session: AsyncSession, test_user: User, test_project: Project
    ):
        """User with PM role should return True."""
        # Add user as PM to project
        team_member = TeamMember(
            id=str(uuid4()),
            user_id=test_user.id,
            project_id=test_project.id,
            role=UserRole.PM.value,
        )
        db_session.add(team_member)
        await db_session.commit()

        result = await check_user_role_for_project(
            db_session, test_user.id, test_project.id, [UserRole.PM]
        )
        assert result is True

    async def test_check_user_role_returns_false_for_developer_when_pm_required(
        self, db_session: AsyncSession, test_user: User, test_project: Project
    ):
        """User with DEVELOPER role should return False when PM required."""
        team_member = TeamMember(
            id=str(uuid4()),
            user_id=test_user.id,
            project_id=test_project.id,
            role=UserRole.DEVELOPER.value,
        )
        db_session.add(team_member)
        await db_session.commit()

        result = await check_user_role_for_project(
            db_session, test_user.id, test_project.id, [UserRole.PM]
        )
        assert result is False

    async def test_check_user_role_accepts_multiple_roles(
        self, db_session: AsyncSession, test_user: User, test_project: Project
    ):
        """Check should accept any of the provided roles."""
        team_member = TeamMember(
            id=str(uuid4()),
            user_id=test_user.id,
            project_id=test_project.id,
            role=UserRole.ADMIN.value,
        )
        db_session.add(team_member)
        await db_session.commit()

        result = await check_user_role_for_project(
            db_session, test_user.id, test_project.id, [UserRole.PM, UserRole.ADMIN]
        )
        assert result is True

    async def test_require_pm_role_raises_for_non_pm(
        self, db_session: AsyncSession, test_user: User, test_project: Project
    ):
        """require_pm_role_for_project should raise 403 for non-PM users."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await require_pm_role_for_project(db_session, test_user, test_project.id)

        assert exc_info.value.status_code == 403
        assert "PM or Admin" in exc_info.value.detail

    async def test_require_pm_role_passes_for_pm(
        self, db_session: AsyncSession, test_user: User, test_project: Project
    ):
        """require_pm_role_for_project should pass for PM users."""
        team_member = TeamMember(
            id=str(uuid4()),
            user_id=test_user.id,
            project_id=test_project.id,
            role=UserRole.PM.value,
        )
        db_session.add(team_member)
        await db_session.commit()

        # Should not raise
        await require_pm_role_for_project(db_session, test_user, test_project.id)

    async def test_require_pm_role_passes_for_superuser(
        self, db_session: AsyncSession, superuser: User, test_project: Project
    ):
        """require_pm_role_for_project should pass for superusers without membership."""
        # Superuser has no team membership but should still pass
        await require_pm_role_for_project(db_session, superuser, test_project.id)


class TestPlanStatusWorkflow:
    """Tests for plan status transitions."""

    @pytest.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        user = User(
            id=str(uuid4()),
            email="pm@example.com",
            username="pmuser",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest.fixture
    async def test_project(self, db_session: AsyncSession, test_user: User) -> Project:
        """Create a test project."""
        project = Project(
            id=str(uuid4()),
            name="Test Project",
            owner_id=test_user.id,
        )
        db_session.add(project)
        await db_session.commit()
        return project

    @pytest.fixture
    async def draft_plan(self, db_session: AsyncSession, test_project: Project) -> Plan:
        """Create a draft plan."""
        plan = Plan(
            id=str(uuid4()),
            task_id=str(uuid4()),
            project_id=test_project.id,
            plan_data={"steps": ["step1", "step2"]},
            status=PlanStatus.DRAFT.value,
        )
        db_session.add(plan)
        await db_session.commit()
        return plan

    async def test_plan_starts_in_draft_status(self, db_session: AsyncSession, draft_plan: Plan):
        """New plans should start in DRAFT status."""
        assert draft_plan.status == PlanStatus.DRAFT.value

    async def test_plan_can_transition_to_pending_approval(
        self, db_session: AsyncSession, draft_plan: Plan
    ):
        """Draft plans can be submitted for approval."""
        draft_plan.status = PlanStatus.PENDING_PM_APPROVAL.value
        await db_session.commit()
        await db_session.refresh(draft_plan)

        assert draft_plan.status == PlanStatus.PENDING_PM_APPROVAL.value

    async def test_plan_can_be_approved(
        self, db_session: AsyncSession, draft_plan: Plan, test_user: User
    ):
        """Pending plans can be approved."""
        draft_plan.status = PlanStatus.PENDING_PM_APPROVAL.value
        await db_session.commit()

        draft_plan.status = PlanStatus.APPROVED.value
        draft_plan.approved_by_id = test_user.id
        await db_session.commit()
        await db_session.refresh(draft_plan)

        assert draft_plan.status == PlanStatus.APPROVED.value
        assert draft_plan.approved_by_id == test_user.id

    async def test_plan_can_be_rejected_with_reason(
        self, db_session: AsyncSession, draft_plan: Plan
    ):
        """Pending plans can be rejected with a reason."""
        draft_plan.status = PlanStatus.PENDING_PM_APPROVAL.value
        await db_session.commit()

        draft_plan.status = PlanStatus.REJECTED.value
        draft_plan.rejection_reason = "Needs more detail on step 2"
        await db_session.commit()
        await db_session.refresh(draft_plan)

        assert draft_plan.status == PlanStatus.REJECTED.value
        assert draft_plan.rejection_reason == "Needs more detail on step 2"
