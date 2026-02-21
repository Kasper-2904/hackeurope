"""Marketplace API routes."""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.storage.database import get_db
from src.storage.models import User
from src.services.marketplace_service import get_marketplace_service
from src.api.schemas_marketplace import (
    AgentPublishRequest,
    MarketplaceAgentResponse,
    AgentSubscribeRequest,
    AgentSubscriptionResponse,
)
from src.storage.models import User, Team, MarketplaceAgent, AgentSubscription
from src.core.state import SubscriptionStatus
from sqlalchemy import select
import uuid

marketplace_router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


@marketplace_router.post(
    "/publish",
    response_model=MarketplaceAgentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_agent(
    publish_data: AgentPublishRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Publish a seller-hosted agent to the marketplace.

    The seller provides:
    - inference_endpoint: URL of their hosted agent
    - access_token: Token for the platform to authenticate with their agent
    - skills: List of skills the agent provides
    """
    service = get_marketplace_service()
    try:
        marketplace_agent = await service.publish_agent(
            db=db,
            seller_id=current_user.id,
            name=publish_data.name,
            category=publish_data.category,
            description=publish_data.description,
            pricing_type=publish_data.pricing_type,
            price_per_use=publish_data.price_per_use,
            inference_endpoint=publish_data.inference_endpoint,
            access_token=publish_data.access_token,
            inference_provider=publish_data.inference_provider,
            inference_model=publish_data.inference_model,
            system_prompt=publish_data.system_prompt,
            skills=publish_data.skills,
        )
        return marketplace_agent
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@marketplace_router.get("/catalog", response_model=List[MarketplaceAgentResponse])
async def list_catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Optional[str] = None,
):
    """Browse the public agent marketplace catalog with agent details."""
    service = get_marketplace_service()
    agents = await service.list_public_agents(db=db, category=category)
    return agents


@marketplace_router.get("/catalog/{marketplace_agent_id}", response_model=MarketplaceAgentResponse)
async def get_marketplace_agent(
    marketplace_agent_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a single marketplace agent with full agent details."""
    service = get_marketplace_service()
    agent = await service.get_marketplace_agent(db=db, marketplace_agent_id=marketplace_agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Marketplace agent not found"
        )
    return agent


@marketplace_router.post(
    "/subscribe/{marketplace_agent_id}", response_model=AgentSubscriptionResponse
)
async def subscribe_to_agent(
    marketplace_agent_id: str,
    req: AgentSubscribeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Subscribe a team to a marketplace agent."""
    # Verify team ownership
    result = await db.execute(
        select(Team).where(Team.id == req.team_id, Team.owner_id == current_user.id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # Verify agent exists
    result = await db.execute(
        select(MarketplaceAgent).where(MarketplaceAgent.id == marketplace_agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Marketplace agent not found"
        )

    # Check if already subscribed
    result = await db.execute(
        select(AgentSubscription).where(
            AgentSubscription.team_id == req.team_id,
            AgentSubscription.marketplace_agent_id == marketplace_agent_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team is already subscribed to this agent",
        )

    # Create subscription
    sub = AgentSubscription(
        id=str(uuid.uuid4()),
        team_id=req.team_id,
        marketplace_agent_id=marketplace_agent_id,
        status=SubscriptionStatus.ACTIVE.value,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub
