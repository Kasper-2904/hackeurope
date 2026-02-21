"""Tests for PaidService (M3-T2: Paid.ai Usage Metering)."""

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.paid_service import PaidService
from src.storage.models import Team, UsageRecord, User


# ============== Helpers ==============


async def _make_user(db: AsyncSession) -> User:
    user = User(
        id=str(uuid4()),
        email=f"paid-{uuid4().hex[:6]}@test.com",
        username=f"paid-user-{uuid4().hex[:6]}",
        hashed_password="fakehash",
    )
    db.add(user)
    await db.flush()
    return user


async def _make_team(db: AsyncSession, owner_id: str) -> Team:
    team = Team(id=str(uuid4()), name="Test Team", owner_id=owner_id)
    db.add(team)
    await db.flush()
    return team


def _make_service(paid_api_key: str = "", paid_product_id: str = "", daily_limit: int = 10) -> PaidService:
    """Create a PaidService with mocked settings (no real Paid.ai client)."""
    mock_settings = MagicMock(
        paid_api_key=paid_api_key,
        paid_product_id=paid_product_id,
        free_tier_daily_limit=daily_limit,
    )
    with patch("src.services.paid_service.get_settings", return_value=mock_settings):
        service = PaidService(settings=mock_settings)
    return service


# ============== Happy Path ==============


@pytest.mark.asyncio
async def test_track_usage_creates_local_record(db_session: AsyncSession):
    """track_usage() always creates a local UsageRecord."""
    user = await _make_user(db_session)
    team = await _make_team(db_session, user.id)

    service = _make_service()  # No API key — disabled
    record = await service.track_usage(
        db=db_session,
        team_id=team.id,
        user_id=user.id,
        usage_type="plan_generation",
        data={"task_id": "t1"},
    )

    assert record.id is not None
    assert record.team_id == team.id
    assert record.user_id == user.id
    assert record.usage_type == "plan_generation"
    assert record.paid_signal_id is None  # No Paid.ai key

    # Verify it's in the DB
    result = await db_session.execute(
        select(UsageRecord).where(UsageRecord.id == record.id)
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_track_usage_with_paid_enabled(db_session: AsyncSession):
    """When Paid.ai is configured, track_usage sends signal and records signal_id."""
    user = await _make_user(db_session)
    team = await _make_team(db_session, user.id)

    mock_client = MagicMock()
    # get_customer_by_external_id raises (not found) → falls through to create
    mock_client.customers.get_customer_by_external_id.side_effect = Exception("not found")
    mock_client.customers.create_customer.return_value = MagicMock(id="cust_123")
    mock_client.orders.create_order.return_value = MagicMock(id="order_456")
    mock_client.signals.create_signals.return_value = MagicMock(__str__=lambda self: "ingested=1")

    service = _make_service(paid_api_key="test-key", paid_product_id="prod_abc")
    service._client = mock_client
    service._enabled = True

    record = await service.track_usage(
        db=db_session,
        team_id=team.id,
        user_id=user.id,
        usage_type="tool_call",
    )

    assert record.paid_signal_id is not None
    mock_client.customers.get_customer_by_external_id.assert_called_once()
    mock_client.customers.create_customer.assert_called_once()
    mock_client.orders.create_order.assert_called_once()
    mock_client.signals.create_signals.assert_called_once()


# ============== Usage Limits ==============


@pytest.mark.asyncio
async def test_check_usage_limit_within_limit(db_session: AsyncSession):
    """check_usage_limit returns True when under the daily limit."""
    user = await _make_user(db_session)
    team = await _make_team(db_session, user.id)

    service = _make_service(daily_limit=10)
    result = await service.check_usage_limit(team.id, db_session)

    assert result is True


@pytest.mark.asyncio
async def test_check_usage_limit_exceeded(db_session: AsyncSession):
    """check_usage_limit returns False when daily limit is reached."""
    user = await _make_user(db_session)
    team = await _make_team(db_session, user.id)

    # Insert 10 records for today
    for _ in range(10):
        db_session.add(
            UsageRecord(
                id=str(uuid4()),
                team_id=team.id,
                usage_type="tool_call",
                quantity=1,
                cost=0.0,
            )
        )
    await db_session.flush()

    service = _make_service(daily_limit=10)
    result = await service.check_usage_limit(team.id, db_session)

    assert result is False


# ============== Error Path ==============


@pytest.mark.asyncio
async def test_track_usage_survives_paid_api_error(db_session: AsyncSession):
    """Even if Paid.ai SDK throws, the local record is still saved."""
    user = await _make_user(db_session)
    team = await _make_team(db_session, user.id)

    mock_client = MagicMock()
    # Both get and create fail
    mock_client.customers.get_customer_by_external_id.side_effect = Exception("not found")
    mock_client.customers.create_customer.side_effect = Exception("Paid.ai is down")

    service = _make_service(paid_api_key="test-key")
    service._client = mock_client
    service._enabled = True

    record = await service.track_usage(
        db=db_session,
        team_id=team.id,
        user_id=user.id,
        usage_type="plan_generation",
    )

    assert record.id is not None
    assert record.paid_signal_id is None  # Failed, but record still saved


@pytest.mark.asyncio
async def test_graceful_degradation_no_api_key(db_session: AsyncSession):
    """When paid_api_key is empty, service skips all SDK calls."""
    user = await _make_user(db_session)
    team = await _make_team(db_session, user.id)

    service = _make_service()

    assert service._enabled is False
    assert service._client is None

    record = await service.track_usage(
        db=db_session,
        team_id=team.id,
        usage_type="tool_call",
    )
    assert record.paid_signal_id is None
    assert record.usage_type == "tool_call"


# ============== Auth Path ==============


@pytest.mark.asyncio
async def test_usage_endpoint_requires_auth():
    """GET /api/v1/billing/usage returns 401 without a token."""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/billing/usage")

    assert resp.status_code in (401, 403)
