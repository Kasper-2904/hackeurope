"""Marketplace API routes."""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.storage.database import get_db
from src.storage.models import User
from src.services.marketplace_service import get_marketplace_service
from src.services.stripe_service import get_stripe_service
from src.api.schemas_marketplace import (
    AgentPublishRequest,
    MarketplaceAgentResponse,
    AgentSubscribeRequest,
    AgentSubscriptionResponse,
)
from src.storage.models import User, Team, MarketplaceAgent, AgentSubscription, SellerProfile
from src.core.state import PricingType, SubscriptionStatus
from sqlalchemy import select
import uuid

marketplace_router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


@marketplace_router.post(
    "/publish",
    status_code=status.HTTP_201_CREATED,
)
async def publish_agent(
    publish_data: AgentPublishRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    return_url: Optional[str] = Query(None, description="Return URL after Stripe onboarding"),
    refresh_url: Optional[str] = Query(None, description="Refresh URL for Stripe onboarding"),
):
    """
    Publish a seller-hosted agent to the marketplace.

    The seller provides:
    - inference_endpoint: URL of their hosted agent
    - access_token: Token for the platform to authenticate with their agent
    - skills: List of skills the agent provides

    For PAID agents:
    - If seller has no Stripe Connect account, returns onboarding_required with URL
    - If seller has incomplete Connect account, returns onboarding_required with URL
    - Requires return_url and refresh_url query params for onboarding flow
    """
    # For paid agents, check seller's Stripe Connect status first
    if (
        publish_data.pricing_type == PricingType.USAGE_BASED
        and publish_data.price_per_use
        and publish_data.price_per_use > 0
    ):
        # Check if seller has a valid Stripe Connect account
        result = await db.execute(
            select(SellerProfile).where(SellerProfile.user_id == current_user.id)
        )
        seller_profile = result.scalar_one_or_none()

        needs_onboarding = False
        stripe_service = get_stripe_service()

        if not seller_profile or not seller_profile.stripe_account_id:
            needs_onboarding = True
        else:
            # Check if the account is fully set up for payouts
            try:
                account_status = stripe_service.get_account_status(seller_profile.stripe_account_id)
                if not account_status.get("charges_enabled") or not account_status.get(
                    "details_submitted"
                ):
                    needs_onboarding = True
            except Exception:
                needs_onboarding = True

        if needs_onboarding:
            # Seller needs to complete Stripe Connect onboarding
            if not return_url or not refresh_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Paid agents require Stripe Connect setup. Provide return_url and refresh_url query parameters.",
                )

            try:
                if not seller_profile or not seller_profile.stripe_account_id:
                    # Create new Connect account
                    account_id = stripe_service.create_connect_account(
                        user_id=current_user.id, email=current_user.email
                    )

                    # Create or update seller profile
                    if seller_profile:
                        seller_profile.stripe_account_id = account_id
                    else:
                        seller_profile = SellerProfile(
                            id=str(uuid.uuid4()),
                            user_id=current_user.id,
                            stripe_account_id=account_id,
                        )
                        db.add(seller_profile)

                    await db.commit()
                else:
                    account_id = seller_profile.stripe_account_id

                # Create onboarding link
                onboarding_url = stripe_service.create_account_link(
                    account_id=account_id,
                    refresh_url=refresh_url,
                    return_url=return_url,
                )

                return {
                    "onboarding_required": True,
                    "onboarding_url": onboarding_url,
                    "stripe_account_id": account_id,
                    "message": "Complete Stripe Connect onboarding to publish paid agents",
                }
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create Stripe Connect onboarding: {str(e)}",
                )

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
        # Return the marketplace agent in response format
        return MarketplaceAgentResponse.model_validate(marketplace_agent)
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


@marketplace_router.post("/subscribe/{marketplace_agent_id}")
async def subscribe_to_agent(
    marketplace_agent_id: str,
    req: AgentSubscribeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Subscribe a team to a marketplace agent.

    For FREE agents: Creates subscription directly and returns AgentSubscriptionResponse.
    For PAID agents: Creates Stripe checkout session and returns checkout_url.
    """
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
    marketplace_agent = result.scalar_one_or_none()
    if not marketplace_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Marketplace agent not found"
        )

    # Check if already subscribed (only check ACTIVE subscriptions)
    result = await db.execute(
        select(AgentSubscription).where(
            AgentSubscription.team_id == req.team_id,
            AgentSubscription.marketplace_agent_id == marketplace_agent_id,
            AgentSubscription.status == SubscriptionStatus.ACTIVE.value,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team already has an active subscription to this agent",
        )

    # FREE agents - create subscription directly
    if marketplace_agent.pricing_type == PricingType.FREE.value:
        sub = AgentSubscription(
            id=str(uuid.uuid4()),
            team_id=req.team_id,
            marketplace_agent_id=marketplace_agent_id,
            status=SubscriptionStatus.ACTIVE.value,
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return {
            "id": sub.id,
            "team_id": sub.team_id,
            "marketplace_agent_id": sub.marketplace_agent_id,
            "status": sub.status,
        }

    # PAID agents - require Stripe checkout
    if not req.success_url or not req.cancel_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="success_url and cancel_url are required for paid agents",
        )

    if not marketplace_agent.stripe_product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent is not configured for payments yet",
        )

    # Get seller's Stripe account for transfers
    seller_stripe_account_id = None
    result = await db.execute(
        select(SellerProfile).where(SellerProfile.user_id == marketplace_agent.seller_id)
    )
    seller_profile = result.scalar_one_or_none()
    if seller_profile and seller_profile.stripe_account_id:
        seller_stripe_account_id = seller_profile.stripe_account_id

    stripe_service = get_stripe_service()

    try:
        checkout_url = stripe_service.create_marketplace_checkout_session(
            team_id=req.team_id,
            marketplace_agent_id=marketplace_agent_id,
            price_id=marketplace_agent.stripe_product_id,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            seller_stripe_account_id=seller_stripe_account_id,
        )
        return {
            "status": "payment_required",
            "checkout_url": checkout_url,
            "message": "Complete payment to activate subscription",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        )
