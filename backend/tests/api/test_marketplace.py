"""Tests for marketplace API endpoints."""

import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.marketplace import list_catalog, get_marketplace_agent, subscribe_to_agent
from src.api.schemas_marketplace import AgentSubscribeRequest
from src.services.marketplace_service import MarketplaceService
from src.core.state import PricingType
from src.storage.models import Team, User


async def _make_user(db: AsyncSession, username: str = "mkt_user", email: str = "mkt@test.com") -> User:
    user = User(
        id=str(uuid4()),
        username=username,
        email=email,
        hashed_password="hashed",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_team(db: AsyncSession, owner: User) -> Team:
    team = Team(id=str(uuid4()), name="Mkt Team", owner_id=owner.id)
    db.add(team)
    await db.flush()
    return team


async def _publish_agent(db: AsyncSession, seller: User, name: str, category: str = "coder") -> object:
    return await MarketplaceService.publish_agent(
        db=db,
        seller_id=seller.id,
        name=name,
        category=category,
        inference_endpoint=f"https://{name.lower().replace(' ', '-')}.example.com/v1",
        access_token=f"token_{name}",
        pricing_type=PricingType.FREE,
    )


class TestMarketplaceCatalog:
    @pytest.mark.asyncio
    async def test_list_catalog(self, db_session: AsyncSession):
        seller = await _make_user(db_session)
        await db_session.commit()

        await _publish_agent(db_session, seller, "Agent A")
        await _publish_agent(db_session, seller, "Agent B")

        agents = await list_catalog(db=db_session)

        assert len(agents) == 2

    @pytest.mark.asyncio
    async def test_list_catalog_filter_by_category(self, db_session: AsyncSession):
        seller = await _make_user(db_session)
        await db_session.commit()

        await _publish_agent(db_session, seller, "Coder 1", category="coder")
        await _publish_agent(db_session, seller, "Reviewer 1", category="reviewer")

        coders = await list_catalog(db=db_session, category="coder")
        reviewers = await list_catalog(db=db_session, category="reviewer")

        assert len(coders) == 1
        assert len(reviewers) == 1

    @pytest.mark.asyncio
    async def test_get_marketplace_agent(self, db_session: AsyncSession):
        seller = await _make_user(db_session)
        await db_session.commit()

        created = await _publish_agent(db_session, seller, "Fetch Me")

        fetched = await get_marketplace_agent(
            marketplace_agent_id=created.id, db=db_session
        )

        assert fetched.id == created.id
        assert fetched.name == "Fetch Me"

    @pytest.mark.asyncio
    async def test_get_marketplace_agent_not_found(self, db_session: AsyncSession):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_marketplace_agent(
                marketplace_agent_id="nonexistent", db=db_session
            )

        assert exc_info.value.status_code == 404


class TestMarketplaceSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_free_agent(self, db_session: AsyncSession):
        owner = await _make_user(db_session)
        team = await _make_team(db_session, owner)
        await db_session.commit()

        agent = await _publish_agent(db_session, owner, "Free Agent")

        result = await subscribe_to_agent(
            marketplace_agent_id=agent.id,
            req=AgentSubscribeRequest(team_id=team.id),
            current_user=owner,
            db=db_session,
        )

        assert result["status"] == "active"
        assert result["team_id"] == team.id

    @pytest.mark.asyncio
    async def test_subscribe_duplicate_400(self, db_session: AsyncSession):
        owner = await _make_user(db_session)
        team = await _make_team(db_session, owner)
        await db_session.commit()

        agent = await _publish_agent(db_session, owner, "Dup Agent")

        # First subscribe
        await subscribe_to_agent(
            marketplace_agent_id=agent.id,
            req=AgentSubscribeRequest(team_id=team.id),
            current_user=owner,
            db=db_session,
        )

        # Second subscribe should fail
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await subscribe_to_agent(
                marketplace_agent_id=agent.id,
                req=AgentSubscribeRequest(team_id=team.id),
                current_user=owner,
                db=db_session,
            )

        assert exc_info.value.status_code == 400
        assert "already" in exc_info.value.detail.lower()
