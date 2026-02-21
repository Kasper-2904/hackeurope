"""Marketplace service for managing agent listings and access."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.models import MarketplaceAgent, Agent
from src.core.state import PricingType
from uuid import uuid4


class MarketplaceService:
    @staticmethod
    async def publish_agent(
        db: AsyncSession,
        agent_id: str,
        seller_id: str,
        name: str,
        category: str,
        description: Optional[str] = None,
        pricing_type: PricingType = PricingType.FREE,
        price_per_use: Optional[float] = None,
    ) -> MarketplaceAgent:
        # Check if agent exists and belongs to seller
        result = await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.owner_id == seller_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found or not owned by you.")

        # Create marketplace listing
        marketplace_agent = MarketplaceAgent(
            id=str(uuid4()),
            agent_id=agent_id,
            seller_id=seller_id,
            name=name,
            description=description,
            category=category,
            pricing_type=pricing_type.value,
            price_per_use=price_per_use,
            is_active=True,
            is_verified=False,
        )

        db.add(marketplace_agent)
        await db.commit()
        await db.refresh(marketplace_agent)
        return marketplace_agent

    @staticmethod
    async def list_public_agents(
        db: AsyncSession, category: Optional[str] = None
    ) -> List[MarketplaceAgent]:
        query = select(MarketplaceAgent).where(MarketplaceAgent.is_active == True)
        if category:
            query = query.where(MarketplaceAgent.category == category)

        result = await db.execute(query)
        return list(result.scalars().all())


def get_marketplace_service() -> MarketplaceService:
    return MarketplaceService()
