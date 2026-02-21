"""Billing and monetization API routes."""

from typing import Annotated, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.api.auth import get_current_user
from src.storage.database import get_db
from src.storage.models import User, Team
from src.services.stripe_service import get_stripe_service
from src.api.schemas_marketplace import SubscriptionCreateRequest, SellerOnboardRequest

billing_router = APIRouter(prefix="/billing", tags=["Billing"])


@billing_router.post("/subscribe")
async def create_subscription(
    req: SubscriptionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a checkout session for team seat subscription."""
    # Verify team ownership
    result = await db.execute(
        select(Team).where(Team.id == req.team_id, Team.owner_id == current_user.id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    stripe_service = get_stripe_service()
    # Dummy price ID for MVP
    PRICE_ID = "price_1dummy"

    try:
        url = stripe_service.create_checkout_session(
            team_id=team.id,
            price_id=PRICE_ID,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
        )
        return {"checkout_url": url}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@billing_router.post("/onboard-seller")
async def onboard_seller(
    req: SellerOnboardRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a Stripe Connect onboarding link for the user."""
    stripe_service = get_stripe_service()
    try:
        account_id = stripe_service.create_connect_account(
            user_id=current_user.id, email=current_user.email
        )
        link_url = stripe_service.create_account_link(
            account_id=account_id, refresh_url=req.refresh_url, return_url=req.return_url
        )
        return {"onboarding_url": link_url}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
