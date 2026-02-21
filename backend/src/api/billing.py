"""Billing and monetization API routes."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.schemas_marketplace import SellerOnboardRequest, SubscriptionCreateRequest
from src.config import get_settings
from src.core.state import PricingType, SubscriptionStatus
from src.services.stripe_service import get_stripe_service
from src.storage.database import get_db
from src.storage.models import (
    AgentSubscription,
    MarketplaceAgent,
    SellerProfile,
    Team,
    User,
    UsageRecord,
)

billing_router = APIRouter(prefix="/billing", tags=["Billing"])


# ============== Team Subscription (Platform Seats) ==============


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

    # TODO: Replace with actual Stripe price ID from environment/config
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


# ============== Marketplace Agent Purchase ==============


@billing_router.post("/purchase-agent/{marketplace_agent_id}")
async def purchase_marketplace_agent(
    marketplace_agent_id: str,
    team_id: str,
    success_url: str,
    cancel_url: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a checkout session to purchase access to a marketplace agent.

    For FREE agents, creates subscription directly.
    For USAGE_BASED agents, creates a Stripe checkout session.
    """
    # Verify team ownership
    result = await db.execute(
        select(Team).where(Team.id == team_id, Team.owner_id == current_user.id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    # Get marketplace agent
    result = await db.execute(
        select(MarketplaceAgent).where(MarketplaceAgent.id == marketplace_agent_id)
    )
    marketplace_agent = result.scalar_one_or_none()
    if not marketplace_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Marketplace agent not found"
        )

    # Check if already subscribed
    result = await db.execute(
        select(AgentSubscription).where(
            AgentSubscription.team_id == team_id,
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
        subscription = AgentSubscription(
            id=str(uuid4()),
            team_id=team_id,
            marketplace_agent_id=marketplace_agent_id,
            status=SubscriptionStatus.ACTIVE.value,
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

        return {
            "status": "subscribed",
            "subscription_id": subscription.id,
            "message": "Successfully subscribed to free agent",
        }

    # USAGE_BASED agents - need Stripe checkout
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
        # stripe_product_id stores the price_id for now
        checkout_url = stripe_service.create_marketplace_checkout_session(
            team_id=team_id,
            marketplace_agent_id=marketplace_agent_id,
            price_id=marketplace_agent.stripe_product_id,
            success_url=success_url,
            cancel_url=cancel_url,
            seller_stripe_account_id=seller_stripe_account_id,
        )
        return {"checkout_url": checkout_url}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ============== Seller Onboarding (Stripe Connect) ==============


@billing_router.post("/onboard-seller")
async def onboard_seller(
    req: SellerOnboardRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a Stripe Connect onboarding link for the user.

    Creates a SellerProfile if one doesn't exist.
    """
    stripe_service = get_stripe_service()

    # Check if seller profile already exists
    result = await db.execute(select(SellerProfile).where(SellerProfile.user_id == current_user.id))
    seller_profile = result.scalar_one_or_none()

    try:
        if seller_profile and seller_profile.stripe_account_id:
            # Already has Connect account, create new link for updating
            link_url = stripe_service.create_account_link(
                account_id=seller_profile.stripe_account_id,
                refresh_url=req.refresh_url,
                return_url=req.return_url,
            )
        else:
            # Create new Connect account
            account_id = stripe_service.create_connect_account(
                user_id=current_user.id, email=current_user.email
            )

            # Create or update seller profile
            if seller_profile:
                seller_profile.stripe_account_id = account_id
            else:
                seller_profile = SellerProfile(
                    id=str(uuid4()),
                    user_id=current_user.id,
                    stripe_account_id=account_id,
                )
                db.add(seller_profile)

            await db.commit()

            link_url = stripe_service.create_account_link(
                account_id=account_id,
                refresh_url=req.refresh_url,
                return_url=req.return_url,
            )

        return {"onboarding_url": link_url, "account_id": seller_profile.stripe_account_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@billing_router.get("/seller-status")
async def get_seller_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the current user's seller profile and Stripe Connect status."""
    result = await db.execute(select(SellerProfile).where(SellerProfile.user_id == current_user.id))
    seller_profile = result.scalar_one_or_none()

    if not seller_profile:
        return {
            "is_seller": False,
            "stripe_connected": False,
            "payout_enabled": False,
        }

    # If has Stripe account, check its status
    if seller_profile.stripe_account_id:
        try:
            stripe_service = get_stripe_service()
            account_status = stripe_service.get_account_status(seller_profile.stripe_account_id)

            # Update payout_enabled based on Stripe status
            if account_status["payouts_enabled"] != seller_profile.payout_enabled:
                seller_profile.payout_enabled = account_status["payouts_enabled"]
                await db.commit()

            return {
                "is_seller": True,
                "stripe_connected": True,
                "stripe_account_id": seller_profile.stripe_account_id,
                "charges_enabled": account_status["charges_enabled"],
                "payouts_enabled": account_status["payouts_enabled"],
                "details_submitted": account_status["details_submitted"],
                "total_earnings": seller_profile.total_earnings,
            }
        except Exception:
            pass

    return {
        "is_seller": True,
        "stripe_connected": bool(seller_profile.stripe_account_id),
        "payout_enabled": seller_profile.payout_enabled,
        "total_earnings": seller_profile.total_earnings,
    }


# ============== Usage Metering (Paid.ai) ==============


@billing_router.get("/usage")
async def get_usage(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    team_id: str | None = None,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """Get usage records for the current user's teams."""
    if team_id:
        team_result = await db.execute(
            select(Team).where(Team.id == team_id, Team.owner_id == current_user.id)
        )
        if not team_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        team_ids = [team_id]
    else:
        teams_result = await db.execute(
            select(Team.id).where(Team.owner_id == current_user.id)
        )
        team_ids = [row[0] for row in teams_result.all()]
        team_ids.append(f"user_{current_user.id}")

    if not team_ids:
        return {"records": [], "total_count": 0, "total_cost": 0.0, "today_count": 0, "daily_limit": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(UsageRecord)
        .where(UsageRecord.team_id.in_(team_ids), UsageRecord.created_at >= cutoff)
        .order_by(UsageRecord.created_at.desc())
        .limit(500)
    )
    records = result.scalars().all()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(UsageRecord.id)).where(
            UsageRecord.team_id.in_(team_ids),
            UsageRecord.created_at >= today_start,
        )
    )
    today_count = today_result.scalar() or 0

    settings = get_settings()

    return {
        "records": [
            {
                "id": r.id,
                "team_id": r.team_id,
                "usage_type": r.usage_type,
                "quantity": r.quantity,
                "cost": r.cost,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
        "records_returned": len(records),
        "total_cost": sum(r.cost for r in records),
        "today_count": today_count,
        "daily_limit": settings.free_tier_daily_limit,
    }


# ============== Stripe Webhooks ==============


@billing_router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Handle Stripe webhook events.

    Events handled:
    - checkout.session.completed: Activate agent subscription after payment
    - account.updated: Update seller Connect account status
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing signature")

    stripe_service = get_stripe_service()

    try:
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await _handle_checkout_completed(session, db)

    elif event["type"] == "account.updated":
        account = event["data"]["object"]
        await _handle_account_updated(account, db)

    return {"status": "ok"}


async def _handle_checkout_completed(session: dict, db: AsyncSession):
    """Handle successful checkout - activate agent subscription."""
    metadata = session.get("metadata", {})

    # Check if this is a marketplace agent purchase
    if metadata.get("type") != "marketplace_agent_purchase":
        return

    team_id = metadata.get("team_id")
    marketplace_agent_id = metadata.get("marketplace_agent_id")

    if not team_id or not marketplace_agent_id:
        return

    # Create the subscription
    subscription = AgentSubscription(
        id=str(uuid4()),
        team_id=team_id,
        marketplace_agent_id=marketplace_agent_id,
        status=SubscriptionStatus.ACTIVE.value,
        stripe_subscription_id=session.get("subscription"),
        paid_order_id=session.get("payment_intent"),
    )
    db.add(subscription)
    await db.commit()


async def _handle_account_updated(account: dict, db: AsyncSession):
    """Handle Connect account update - update seller profile."""
    account_id = account.get("id")

    result = await db.execute(
        select(SellerProfile).where(SellerProfile.stripe_account_id == account_id)
    )
    seller_profile = result.scalar_one_or_none()

    if seller_profile:
        seller_profile.payout_enabled = account.get("payouts_enabled", False)
        await db.commit()
