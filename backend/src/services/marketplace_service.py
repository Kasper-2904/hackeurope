"""Marketplace service for managing agent listings and access."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.models import MarketplaceAgent, Agent, SellerProfile, User
from src.core.state import PricingType, AgentStatus
from src.services.stripe_service import get_stripe_service
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

        For paid agents, also creates a Stripe Product and Price.
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

        # For paid agents, create Stripe product and price
        stripe_product_id = None
        if pricing_type == PricingType.USAGE_BASED and price_per_use and price_per_use > 0:
            # Get seller's Stripe account if they have one
            seller_stripe_account_id = None
            result = await db.execute(
                select(SellerProfile).where(SellerProfile.user_id == seller_id)
            )
            seller_profile = result.scalar_one_or_none()
            if seller_profile:
                seller_stripe_account_id = seller_profile.stripe_account_id

            # Create Stripe product and price
            try:
                stripe_service = get_stripe_service()
                product_id, price_id = stripe_service.create_product_and_price(
                    name=name,
                    description=description or f"Access to {name} agent",
                    price_cents=int(price_per_use * 100),  # Convert to cents
                    seller_stripe_account_id=seller_stripe_account_id,
                )
                # Store price_id (we use it for checkout)
                stripe_product_id = price_id
            except Exception as e:
                # Log but don't fail - agent can still be listed, just not purchasable
                print(f"Warning: Failed to create Stripe product: {e}")

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
            stripe_product_id=stripe_product_id,
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
    async def list_public_agents(db: AsyncSession, category: Optional[str] = None) -> List[MarketplaceAgent]:
        query = (
            select(MarketplaceAgent)
            .options(
                selectinload(MarketplaceAgent.agent),
                selectinload(MarketplaceAgent.seller),
            )
            .where(MarketplaceAgent.is_active == True)
        )
        if category:
            query = query.where(MarketplaceAgent.category == category)

        result = await db.execute(query)
        agents = list(result.scalars().all())

        # Set seller_name on each agent for serialization
        for agent in agents:
            agent.seller_name = (
                agent.seller.full_name or agent.seller.username
                if agent.seller
                else None
            )

        return agents

    @staticmethod
    async def get_marketplace_agent(db: AsyncSession, marketplace_agent_id: str) -> Optional[MarketplaceAgent]:
        """Get a single marketplace agent with its linked agent details."""
        query = (
            select(MarketplaceAgent)
            .options(
                selectinload(MarketplaceAgent.agent),
                selectinload(MarketplaceAgent.seller),
            )
            .where(MarketplaceAgent.id == marketplace_agent_id)
        )
        result = await db.execute(query)
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        # Set seller_name for serialization
        agent.seller_name = (
            agent.seller.full_name or agent.seller.username
            if agent.seller
            else None
        )

        return agent


def get_marketplace_service() -> MarketplaceService:
    return MarketplaceService()
