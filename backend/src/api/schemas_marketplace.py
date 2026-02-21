"""Schemas for marketplace and billing."""

from pydantic import BaseModel
from typing import Optional
from src.core.state import PricingType


class AgentPublishRequest(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    pricing_type: PricingType = PricingType.FREE
    price_per_use: Optional[float] = None


class MarketplaceAgentResponse(BaseModel):
    id: str
    agent_id: str
    seller_id: str
    name: str
    category: str
    description: Optional[str]
    pricing_type: str
    price_per_use: Optional[float]
    is_verified: bool
    is_active: bool

    model_config = {"from_attributes": True}


class SubscriptionCreateRequest(BaseModel):
    team_id: str
    success_url: str
    cancel_url: str


class SellerOnboardRequest(BaseModel):
    refresh_url: str
    return_url: str
