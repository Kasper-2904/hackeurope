"""Marketplace API routes."""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.storage.database import get_db
from src.storage.models import User
from src.services.marketplace_service import get_marketplace_service
from src.api.schemas_marketplace import AgentPublishRequest, MarketplaceAgentResponse

marketplace_router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


@marketplace_router.post(
    "/publish/{agent_id}",
    response_model=MarketplaceAgentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_agent(
    agent_id: str,
    publish_data: AgentPublishRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Publish an agent to the marketplace."""
    service = get_marketplace_service()
    try:
        marketplace_agent = await service.publish_agent(
            db=db,
            agent_id=agent_id,
            seller_id=current_user.id,
            name=publish_data.name,
            category=publish_data.category,
            description=publish_data.description,
            pricing_type=publish_data.pricing_type,
            price_per_use=publish_data.price_per_use,
        )
        return marketplace_agent
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@marketplace_router.get("/catalog", response_model=List[MarketplaceAgentResponse])
async def list_catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Optional[str] = None,
):
    """Browse the public agent marketplace catalog."""
    service = get_marketplace_service()
    agents = await service.list_public_agents(db=db, category=category)
    return agents
