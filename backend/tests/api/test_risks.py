"""Tests for risk signals and reviewer API endpoints."""

import pytest
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.risks import create_risk_signal, list_risks, list_project_risks, resolve_risk_signal, get_reviewer_risks
from src.api.schemas import RiskSignalCreate, RiskSignalResolve
from src.core.state import RiskSeverity, RiskSource
from src.storage.models import AuditLog, Project, RiskSignal, User


async def _make_user(db: AsyncSession) -> User:
    user = User(
        id=str(uuid4()),
        username="risk_user",
        email="risk@test.com",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_project(db: AsyncSession, owner: User) -> Project:
    project = Project(id=str(uuid4()), name="Risk Project", owner_id=owner.id)
    db.add(project)
    await db.flush()
    return project


async def _make_risk(db: AsyncSession, project_id: str, resolved: bool = False) -> RiskSignal:
    risk = RiskSignal(
        id=str(uuid4()),
        project_id=project_id,
        source=RiskSource.SECURITY.value,
        severity=RiskSeverity.HIGH.value,
        title="Test risk signal",
        is_resolved=resolved,
    )
    db.add(risk)
    await db.flush()
    return risk


class TestRiskSignals:
    @pytest.mark.asyncio
    async def test_create_risk_signal(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        project = await _make_project(db_session, user)
        await db_session.commit()

        risk = await create_risk_signal(
            risk_data=RiskSignalCreate(
                project_id=project.id,
                source=RiskSource.MERGE_CONFLICT,
                severity=RiskSeverity.CRITICAL,
                title="Merge conflict detected",
                description="Two files overlap.",
            ),
            current_user=user,
            db=db_session,
        )

        assert risk.title == "Merge conflict detected"
        assert risk.severity == RiskSeverity.CRITICAL.value
        assert risk.source == RiskSource.MERGE_CONFLICT.value
        assert risk.is_resolved is False

    @pytest.mark.asyncio
    async def test_list_risks_excludes_resolved(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        project = await _make_project(db_session, user)
        await _make_risk(db_session, project.id, resolved=False)
        await _make_risk(db_session, project.id, resolved=True)
        await db_session.commit()

        risks = await list_risks(current_user=user, db=db_session)

        assert len(risks) == 1
        assert risks[0].is_resolved is False

    @pytest.mark.asyncio
    async def test_list_risks_include_resolved(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        project = await _make_project(db_session, user)
        await _make_risk(db_session, project.id, resolved=False)
        await _make_risk(db_session, project.id, resolved=True)
        await db_session.commit()

        risks = await list_risks(current_user=user, db=db_session, include_resolved=True)

        assert len(risks) == 2

    @pytest.mark.asyncio
    async def test_list_project_risks(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        project = await _make_project(db_session, user)
        await _make_risk(db_session, project.id)
        await db_session.commit()

        risks = await list_project_risks(
            project_id=project.id, current_user=user, db=db_session
        )

        assert len(risks) == 1
        assert risks[0].project_id == project.id

    @pytest.mark.asyncio
    async def test_resolve_risk_signal(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        project = await _make_project(db_session, user)
        risk = await _make_risk(db_session, project.id)
        await db_session.commit()

        resolved = await resolve_risk_signal(
            risk_id=risk.id,
            resolve_data=RiskSignalResolve(resolution_note="Fixed it"),
            current_user=user,
            db=db_session,
        )

        assert resolved.is_resolved is True
        assert resolved.resolved_by_id == user.id

        # Verify audit log was created
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.resource_id == risk.id)
        )
        audit = result.scalar_one()
        assert audit.action == "risk_resolved"

    @pytest.mark.asyncio
    async def test_resolve_risk_not_found(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        await db_session.commit()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await resolve_risk_signal(
                risk_id="nonexistent",
                resolve_data=RiskSignalResolve(resolution_note="nope"),
                current_user=user,
                db=db_session,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_reviewer_get_risks(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        project = await _make_project(db_session, user)
        await _make_risk(db_session, project.id, resolved=False)
        await _make_risk(db_session, project.id, resolved=True)
        await db_session.commit()

        # Reviewer endpoint returns ALL risks (including resolved)
        risks = await get_reviewer_risks(
            project_id=project.id, current_user=user, db=db_session
        )

        assert len(risks) == 2
