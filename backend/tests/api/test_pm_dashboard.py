"""API-level tests for PM dashboard and project allowlist flows (M2-T4)."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.dashboards import pm_dashboard
from src.api.plans import approve_plan, reject_plan
from src.api.projects import (
    add_project_allowed_agent,
    list_project_allowed_agents,
    remove_project_allowed_agent,
)
from src.api.schemas import PlanReject
from src.core.state import PlanStatus, TaskStatus, UserRole
from src.main import create_app
from src.storage.database import get_db
from src.storage.models import Agent, AuditLog, Plan, Project, ProjectAllowedAgent, RiskSignal, Task, TeamMember, User


def _make_user(db: AsyncSession, suffix: str) -> User:
    user = User(
        id=str(uuid4()),
        email=f"{suffix}-{uuid4().hex[:6]}@example.com",
        username=f"{suffix}-{uuid4().hex[:6]}",
        hashed_password="fakehash",
    )
    db.add(user)
    return user


async def _make_project(db: AsyncSession, owner_id: str) -> Project:
    project = Project(
        id=str(uuid4()),
        name="PM Dashboard Project",
        description="Project for PM dashboard tests",
        goals=["Ship PM dashboard"],
        timeline={"start": "2026-02-01", "end": "2026-02-28"},
        owner_id=owner_id,
    )
    db.add(project)
    await db.flush()
    return project


async def _make_agent(db: AsyncSession, owner_id: str, name: str = "Coder Agent") -> Agent:
    agent = Agent(
        id=str(uuid4()),
        name=name,
        role="coder",
        description="Test agent",
        inference_endpoint="https://inference.example.test/v1/chat/completions",
        owner_id=owner_id,
    )
    db.add(agent)
    await db.flush()
    return agent


async def _add_pm_membership(db: AsyncSession, *, user_id: str, project_id: str) -> TeamMember:
    membership = TeamMember(
        id=str(uuid4()),
        user_id=user_id,
        project_id=project_id,
        role=UserRole.PM.value,
        skills=[],
        capacity=1.0,
        current_load=0.0,
    )
    db.add(membership)
    await db.flush()
    return membership


async def _make_task(db: AsyncSession, owner_id: str) -> Task:
    task = Task(
        id=str(uuid4()),
        title="Implement PM dashboard",
        task_type="code_generation",
        created_by_id=owner_id,
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.flush()
    return task


async def _make_plan(db: AsyncSession, project_id: str, task_id: str, status: PlanStatus) -> Plan:
    plan = Plan(
        id=str(uuid4()),
        task_id=task_id,
        project_id=project_id,
        status=status.value,
        plan_data={"summary": "Implement PM dashboard widgets"},
        version=1,
    )
    db.add(plan)
    await db.flush()
    return plan


@pytest.fixture
async def api_client(db_session: AsyncSession):
    app = create_app()
    context: dict[str, User | None] = {"current_user": None}

    async def override_get_db():
        yield db_session

    async def override_get_current_user() -> User:
        user = context["current_user"]
        if user is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, context

    app.dependency_overrides.clear()


async def test_project_allowlist_add_list_remove(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    project = await _make_project(db_session, owner.id)
    agent = await _make_agent(db_session, owner.id)

    added = await add_project_allowed_agent(project.id, agent.id, current_user=owner, db=db_session)
    assert added.project_id == project.id
    assert added.agent_id == agent.id

    listed = await list_project_allowed_agents(project.id, current_user=owner, db=db_session)
    assert len(listed) == 1
    assert listed[0].agent.name == "Coder Agent"

    await remove_project_allowed_agent(project.id, agent.id, current_user=owner, db=db_session)
    listed_after_remove = await list_project_allowed_agents(project.id, current_user=owner, db=db_session)
    assert listed_after_remove == []


async def test_project_allowlist_prevents_duplicates(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    project = await _make_project(db_session, owner.id)
    agent = await _make_agent(db_session, owner.id)

    await add_project_allowed_agent(project.id, agent.id, current_user=owner, db=db_session)

    with pytest.raises(HTTPException) as exc:
        await add_project_allowed_agent(project.id, agent.id, current_user=owner, db=db_session)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Agent is already allowed for this project"


async def test_project_allowlist_add_requires_owned_agent(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    outsider = _make_user(db_session, "outsider")
    project = await _make_project(db_session, owner.id)
    outsider_agent = await _make_agent(db_session, outsider.id)

    with pytest.raises(HTTPException) as exc:
        await add_project_allowed_agent(
            project.id,
            outsider_agent.id,
            current_user=owner,
            db=db_session,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Agent not found"


async def test_project_allowlist_add_invalid_agent_id_returns_not_found(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    project = await _make_project(db_session, owner.id)

    with pytest.raises(HTTPException) as exc:
        await add_project_allowed_agent(project.id, "missing-agent", current_user=owner, db=db_session)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Agent not found"


async def test_project_allowlist_requires_project_owner_for_list_and_remove(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    outsider = _make_user(db_session, "outsider")
    project = await _make_project(db_session, owner.id)
    agent = await _make_agent(db_session, owner.id)
    await add_project_allowed_agent(project.id, agent.id, current_user=owner, db=db_session)

    with pytest.raises(HTTPException) as list_exc:
        await list_project_allowed_agents(project.id, current_user=outsider, db=db_session)
    assert list_exc.value.status_code == 404
    assert list_exc.value.detail == "Project not found"

    with pytest.raises(HTTPException) as remove_exc:
        await remove_project_allowed_agent(project.id, agent.id, current_user=outsider, db=db_session)
    assert remove_exc.value.status_code == 404
    assert remove_exc.value.detail == "Project not found"


async def test_project_allowlist_remove_missing_entry_returns_not_found(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    project = await _make_project(db_session, owner.id)
    agent = await _make_agent(db_session, owner.id)

    with pytest.raises(HTTPException) as exc:
        await remove_project_allowed_agent(project.id, agent.id, current_user=owner, db=db_session)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Allowed agent not found"


async def test_pm_plan_approval_success_requires_owner_and_creates_audit_log(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    outsider = _make_user(db_session, "outsider")
    project = await _make_project(db_session, owner.id)
    await _add_pm_membership(db_session, user_id=owner.id, project_id=project.id)
    task = await _make_task(db_session, owner.id)
    plan = await _make_plan(db_session, project.id, task.id, PlanStatus.PENDING_PM_APPROVAL)

    with pytest.raises(HTTPException) as exc:
        await approve_plan(plan.id, current_user=outsider, db=db_session)
    assert exc.value.status_code == 403

    approved = await approve_plan(plan.id, current_user=owner, db=db_session)
    assert approved.status == PlanStatus.APPROVED.value
    assert approved.approved_by_id == owner.id
    assert approved.approved_at is not None

    audit_result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.resource_id == plan.id,
            AuditLog.action == "plan_approved",
        )
    )
    audit = audit_result.scalar_one()
    assert audit.user_id == owner.id
    assert audit.previous_state == {"status": PlanStatus.PENDING_PM_APPROVAL.value}
    assert audit.new_state == {"status": PlanStatus.APPROVED.value}


async def test_pm_plan_approval_rejects_wrong_status_and_missing_plan(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    project = await _make_project(db_session, owner.id)
    await _add_pm_membership(db_session, user_id=owner.id, project_id=project.id)
    task = await _make_task(db_session, owner.id)
    approved_plan = await _make_plan(db_session, project.id, task.id, PlanStatus.APPROVED)

    with pytest.raises(HTTPException) as missing_exc:
        await approve_plan("missing-plan", current_user=owner, db=db_session)
    assert missing_exc.value.status_code == 404
    assert missing_exc.value.detail == "Plan not found"

    with pytest.raises(HTTPException) as status_exc:
        await approve_plan(approved_plan.id, current_user=owner, db=db_session)
    assert status_exc.value.status_code == 400
    assert status_exc.value.detail == "Plan must be in pending_pm_approval status to be approved"


async def test_pm_plan_reject_success_requires_owner_and_creates_audit_log(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    outsider = _make_user(db_session, "outsider")
    project = await _make_project(db_session, owner.id)
    await _add_pm_membership(db_session, user_id=owner.id, project_id=project.id)
    task = await _make_task(db_session, owner.id)
    plan = await _make_plan(db_session, project.id, task.id, PlanStatus.PENDING_PM_APPROVAL)

    with pytest.raises(HTTPException) as exc:
        await reject_plan(
            plan.id,
            PlanReject(rejection_reason="Need clearer scope"),
            current_user=outsider,
            db=db_session,
        )
    assert exc.value.status_code == 403

    rejected = await reject_plan(
        plan.id,
        PlanReject(rejection_reason="Need clearer scope"),
        current_user=owner,
        db=db_session,
    )
    assert rejected.status == PlanStatus.REJECTED.value
    assert rejected.rejection_reason == "Need clearer scope"

    audit_result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.resource_id == plan.id,
            AuditLog.action == "plan_rejected",
        )
    )
    audit = audit_result.scalar_one()
    assert audit.user_id == owner.id
    assert audit.details["reason"] == "Need clearer scope"
    assert audit.previous_state == {"status": PlanStatus.PENDING_PM_APPROVAL.value}
    assert audit.new_state == {"status": PlanStatus.REJECTED.value}


async def test_pm_plan_reject_rejects_wrong_status_and_missing_plan(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    project = await _make_project(db_session, owner.id)
    await _add_pm_membership(db_session, user_id=owner.id, project_id=project.id)
    task = await _make_task(db_session, owner.id)
    rejected_plan = await _make_plan(db_session, project.id, task.id, PlanStatus.REJECTED)

    with pytest.raises(HTTPException) as missing_exc:
        await reject_plan(
            "missing-plan",
            PlanReject(rejection_reason="Missing risk analysis"),
            current_user=owner,
            db=db_session,
        )
    assert missing_exc.value.status_code == 404
    assert missing_exc.value.detail == "Plan not found"

    with pytest.raises(HTTPException) as status_exc:
        await reject_plan(
            rejected_plan.id,
            PlanReject(rejection_reason="Missing risk analysis"),
            current_user=owner,
            db=db_session,
        )
    assert status_exc.value.status_code == 400
    assert status_exc.value.detail == "Plan must be in pending_pm_approval status to be rejected"


async def test_pm_dashboard_includes_allowlist_and_pending_approvals(db_session: AsyncSession):
    owner = _make_user(db_session, "owner")
    teammate = _make_user(db_session, "teammate")
    project = await _make_project(db_session, owner.id)
    agent = await _make_agent(db_session, owner.id)
    task = await _make_task(db_session, owner.id)
    pending_plan = await _make_plan(db_session, project.id, task.id, PlanStatus.PENDING_PM_APPROVAL)
    await _make_plan(db_session, project.id, task.id, PlanStatus.APPROVED)

    db_session.add(
        TeamMember(
            id=str(uuid4()),
            user_id=teammate.id,
            project_id=project.id,
            role="developer",
            skills=["react"],
            capacity=1.0,
            current_load=0.4,
        )
    )
    db_session.add(
        RiskSignal(
            id=str(uuid4()),
            project_id=project.id,
            source="reviewer",
            severity="high",
            title="Potential integration regression",
        )
    )
    await add_project_allowed_agent(project.id, agent.id, current_user=owner, db=db_session)

    payload = await pm_dashboard(project.id, current_user=owner, db=db_session)

    assert payload["project_id"] == project.id
    assert payload["pending_approvals"][0].id == pending_plan.id
    assert payload["allowed_agents"][0].agent_id == agent.id
    assert payload["tasks_by_status"]["pending"] == 1
    assert len(payload["critical_alerts"]) == 1

    allowlist_result = await db_session.execute(
        select(ProjectAllowedAgent).where(
            ProjectAllowedAgent.project_id == project.id,
            ProjectAllowedAgent.agent_id == agent.id,
        )
    )
    assert allowlist_result.scalar_one().added_by_id == owner.id


async def test_allowlist_endpoints_happy_path_via_http(
    db_session: AsyncSession, api_client: tuple[AsyncClient, dict[str, User | None]]
):
    owner = _make_user(db_session, "owner")
    project = await _make_project(db_session, owner.id)
    agent = await _make_agent(db_session, owner.id)
    await db_session.commit()

    client, context = api_client
    context["current_user"] = owner

    add_response = await client.post(f"/api/v1/projects/{project.id}/allowlist/{agent.id}")
    assert add_response.status_code == 201
    assert add_response.json()["agent_id"] == agent.id

    list_response = await client.get(f"/api/v1/projects/{project.id}/allowlist")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["agent"]["name"] == "Coder Agent"

    remove_response = await client.delete(f"/api/v1/projects/{project.id}/allowlist/{agent.id}")
    assert remove_response.status_code == 204


async def test_allowlist_endpoints_block_non_owner_via_http(
    db_session: AsyncSession, api_client: tuple[AsyncClient, dict[str, User | None]]
):
    owner = _make_user(db_session, "owner")
    outsider = _make_user(db_session, "outsider")
    project = await _make_project(db_session, owner.id)
    agent = await _make_agent(db_session, owner.id)
    await db_session.commit()

    client, context = api_client
    context["current_user"] = outsider

    response = await client.post(f"/api/v1/projects/{project.id}/allowlist/{agent.id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


async def test_plan_reject_endpoint_validates_reason_via_http(
    db_session: AsyncSession, api_client: tuple[AsyncClient, dict[str, User | None]]
):
    owner = _make_user(db_session, "owner")
    project = await _make_project(db_session, owner.id)
    task = await _make_task(db_session, owner.id)
    plan = await _make_plan(db_session, project.id, task.id, PlanStatus.PENDING_PM_APPROVAL)
    await db_session.commit()

    client, context = api_client
    context["current_user"] = owner

    response = await client.post(
        f"/api/v1/plans/{plan.id}/reject",
        json={"rejection_reason": ""},
    )
    assert response.status_code == 422


async def test_pm_dashboard_endpoint_includes_m2_t4_payload_via_http(
    db_session: AsyncSession, api_client: tuple[AsyncClient, dict[str, User | None]]
):
    owner = _make_user(db_session, "owner")
    teammate = _make_user(db_session, "teammate")
    project = await _make_project(db_session, owner.id)
    agent = await _make_agent(db_session, owner.id)
    task = await _make_task(db_session, owner.id)
    pending_plan = await _make_plan(db_session, project.id, task.id, PlanStatus.PENDING_PM_APPROVAL)
    await _make_plan(db_session, project.id, task.id, PlanStatus.APPROVED)

    db_session.add(
        TeamMember(
            id=str(uuid4()),
            user_id=teammate.id,
            project_id=project.id,
            role="developer",
            skills=["react"],
            capacity=1.0,
            current_load=0.4,
        )
    )
    db_session.add(
        RiskSignal(
            id=str(uuid4()),
            project_id=project.id,
            source="reviewer",
            severity="high",
            title="Potential integration regression",
        )
    )
    await add_project_allowed_agent(project.id, agent.id, current_user=owner, db=db_session)
    await db_session.commit()

    client, context = api_client
    context["current_user"] = owner
    response = await client.get(f"/api/v1/dashboard/pm/{project.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == project.id
    assert payload["pending_approvals"][0]["id"] == pending_plan.id
    assert payload["allowed_agents"][0]["agent_id"] == agent.id
    assert payload["tasks_by_status"]["pending"] == 1
    assert len(payload["critical_alerts"]) == 1
