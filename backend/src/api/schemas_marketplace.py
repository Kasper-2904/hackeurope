"""Schemas for marketplace and billing."""

from datetime import datetime
from typing import Optional

from pydantic import AnyHttpUrl, BaseModel
from src.core.state import PricingType


class AgentPublishRequest(BaseModel):
    """Request to publish a seller-hosted agent to the marketplace."""

    name: str
    category: str
    description: Optional[str] = None
    pricing_type: PricingType = PricingType.FREE
    price_per_use: Optional[float] = None

    # Seller's hosted agent connection details
    inference_endpoint: str  # Seller's hosted agent URL (e.g., https://myagent.example.com/v1)
    access_token: str  # Token for platform to authenticate with seller's agent

    # Agent configuration
    inference_provider: str = "custom"  # custom, openai-compatible, anthropic, etc.
    inference_model: Optional[str] = None  # Model name if applicable
    system_prompt: Optional[str] = None  # Default system prompt for the agent
    skills: list[str] = []  # Skills this agent provides


class AgentDetailsResponse(BaseModel):
    """Nested agent details for marketplace response."""

    id: str
    name: str
    role: str
    description: Optional[str]
    inference_endpoint: str
    inference_provider: str
    inference_model: str
    system_prompt: Optional[str]
    skills: list[str]
    status: str

    model_config = {"from_attributes": True}


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

    # Linked agent details
    agent: Optional[AgentDetailsResponse] = None

    model_config = {"from_attributes": True}


class AgentSubscribeRequest(BaseModel):
    team_id: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class AgentSubscriptionResponse(BaseModel):
    id: str
    team_id: str
    marketplace_agent_id: str
    status: str

    model_config = {"from_attributes": True}


class SubscriptionCreateRequest(BaseModel):
    team_id: str
    success_url: AnyHttpUrl
    cancel_url: AnyHttpUrl


class SubscriptionCreateResponse(BaseModel):
    checkout_url: str
    team_id: str


class BillingSubscriptionSnapshotResponse(BaseModel):
    status: str
    active_agent_subscriptions: int
    stripe_subscription_id: str | None = None
    seat_count: int | None = None


class BillingUsageByAgentResponse(BaseModel):
    marketplace_agent_id: str
    marketplace_agent_name: str
    total_quantity: int
    total_cost: float


class BillingUsageRecordResponse(BaseModel):
    id: str
    marketplace_agent_id: str
    marketplace_agent_name: str
    usage_type: str
    quantity: int
    cost: float
    created_at: datetime


class BillingSummaryResponse(BaseModel):
    team_id: str
    subscription: BillingSubscriptionSnapshotResponse
    total_usage_cost: float
    usage_by_agent: list[BillingUsageByAgentResponse]
    recent_usage: list[BillingUsageRecordResponse]


class SellerOnboardRequest(BaseModel):
    refresh_url: str
    return_url: str
