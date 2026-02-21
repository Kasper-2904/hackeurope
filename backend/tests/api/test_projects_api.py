"""Tests for project API behaviors."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.projects import list_projects
from src.storage.models import Project, User


async def _make_user(db: AsyncSession, username: str, email: str) -> User:
    user = User(
        id=str(uuid4()),
        username=username,
        email=email,
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_list_projects_returns_workspace_projects(db_session: AsyncSession):
    owner = await _make_user(db_session, "owner_user", "owner@example.com")
    viewer = await _make_user(db_session, "viewer_user", "viewer@example.com")

    db_session.add(
        Project(
            id=str(uuid4()),
            name="Workspace Project A",
            owner_id=owner.id,
        )
    )
    db_session.add(
        Project(
            id=str(uuid4()),
            name="Workspace Project B",
            owner_id=owner.id,
        )
    )
    await db_session.commit()

    projects = await list_projects(current_user=viewer, db=db_session)
    names = {project.name for project in projects}

    assert "Workspace Project A" in names
    assert "Workspace Project B" in names
