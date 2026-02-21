"""Marketplace service for managing agent listings and access."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.models import MarketplaceAgent, Agent
from src.core.state import PricingType, AgentStatus
from uuid import uuid4


class MarketplaceService:
    @staticmethod
    async def publish_agent(
        db: AsyncSession,
        seller_id: str,
        name: str,
        category: str,
        inference_endpoint: str,
        access_token: str,
        description: Optional[str] = None,
        pricing_type: PricingType = PricingType.FREE,
        price_per_use: Optional[float] = None,
        inference_provider: str = "custom",
        inference_model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        skills: Optional[List[str]] = None,
    ) -> MarketplaceAgent:
        """
        Publish a seller-hosted agent to the marketplace.

        This creates both the Agent record (with seller's endpoint/token)
        and the MarketplaceAgent listing.
        """
        # Create the agent with seller's hosted endpoint
        agent_id = str(uuid4())
        agent = Agent(
            id=agent_id,
            name=name,
            role="custom",  # Seller-hosted agents are custom role
            description=description,
            inference_endpoint=inference_endpoint,
            inference_api_key_encrypted=access_token,  # Seller's access token
            inference_provider=inference_provider,
            inference_model=inference_model or "default",
            system_prompt=system_prompt,
            skills=skills or [],
            owner_id=seller_id,
            status=AgentStatus.ONLINE,
        )
        db.add(agent)

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

        # Attach the agent for response
        marketplace_agent.agent = agent
        return marketplace_agent

    @staticmethod
    async def list_public_agents(
        db: AsyncSession, category: Optional[str] = None
    ) -> List[MarketplaceAgent]:
        query = (
            select(MarketplaceAgent)
            .options(selectinload(MarketplaceAgent.agent))
            .where(MarketplaceAgent.is_active == True)
        )
        if category:
            query = query.where(MarketplaceAgent.category == category)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_marketplace_agent(
        db: AsyncSession, marketplace_agent_id: str
    ) -> Optional[MarketplaceAgent]:
        """Get a single marketplace agent with its linked agent details."""
        query = (
            select(MarketplaceAgent)
            .options(selectinload(MarketplaceAgent.agent))
            .where(MarketplaceAgent.id == marketplace_agent_id)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()


def get_marketplace_service() -> MarketplaceService:
    return MarketplaceService()
