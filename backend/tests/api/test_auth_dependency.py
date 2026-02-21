"""Tests for auth dependency helpers."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_access_token, create_agent_token, get_current_user
from src.storage.models import User


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.asyncio
async def test_get_current_user_returns_user_for_valid_user_token(db_session: AsyncSession):
    user = User(
        id=str(uuid4()),
        email=f"user-{uuid4().hex[:6]}@example.com",
        username=f"user-{uuid4().hex[:6]}",
        hashed_password="hashed",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token({"sub": user.id, "type": "user"})
    current_user = await get_current_user(_bearer(token), db_session)

    assert current_user.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_rejects_agent_tokens(db_session: AsyncSession):
    token = create_agent_token(str(uuid4()))

    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer(token), db_session)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Agent tokens cannot access user endpoints"
