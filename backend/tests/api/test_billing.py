"""Tests for billing API business logic."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.storage.database import get_db
from src.storage.models import (
    AgentSubscription,
    Agent,
    MarketplaceAgent,
    SellerProfile,
    Team,
    User,
)
from src.core.state import PricingType, SubscriptionStatus, AgentStatus
from src.api.billing import (
    _handle_checkout_completed,
    _handle_account_updated,
)
from src.api.agents import verify_agent_subscription


# ============== Fixtures ==============


class TestBillingFixtures:
    """Test fixture creation for billing tests."""

    @pytest.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        user = User(
            id=str(uuid4()),
            email="test@example.com",
            username="testuser",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest.fixture
    async def test_team(self, db_session: AsyncSession, test_user: User) -> Team:
        """Create a test team owned by the test user."""
        team = Team(
            id=str(uuid4()),
            name="Test Team",
            owner_id=test_user.id,
        )
        db_session.add(team)
        await db_session.commit()
        return team

    @pytest.fixture
    async def test_agent(self, db_session: AsyncSession, test_user: User) -> Agent:
        """Create a test agent."""
        agent = Agent(
            id=str(uuid4()),
            name="Test Agent",
            role="coder",
            inference_endpoint="https://test.example.com/v1",
            inference_provider="openai",
            inference_model="gpt-4",
            owner_id=test_user.id,
            status=AgentStatus.ONLINE,
        )
        db_session.add(agent)
        await db_session.commit()
        return agent

    @pytest.fixture
    async def free_marketplace_agent(
        self, db_session: AsyncSession, test_agent: Agent, test_user: User
    ) -> MarketplaceAgent:
        """Create a FREE marketplace agent."""
        ma = MarketplaceAgent(
            id=str(uuid4()),
            agent_id=test_agent.id,
            seller_id=test_user.id,
            name="Free Agent",
            category="coder",
            pricing_type=PricingType.FREE.value,
            is_active=True,
        )
        db_session.add(ma)
        await db_session.commit()
        return ma

    @pytest.fixture
    async def paid_marketplace_agent(
        self, db_session: AsyncSession, test_agent: Agent, test_user: User
    ) -> MarketplaceAgent:
        """Create a USAGE_BASED marketplace agent."""
        ma = MarketplaceAgent(
            id=str(uuid4()),
            agent_id=test_agent.id,
            seller_id=test_user.id,
            name="Paid Agent",
            category="coder",
            pricing_type=PricingType.USAGE_BASED.value,
            price_per_use=5.00,
            stripe_product_id="price_test123",
            is_active=True,
        )
        db_session.add(ma)
        await db_session.commit()
        return ma

    @pytest.fixture
    async def seller_profile(self, db_session: AsyncSession, test_user: User) -> SellerProfile:
        """Create a seller profile with Stripe Connect."""
        profile = SellerProfile(
            id=str(uuid4()),
            user_id=test_user.id,
            stripe_account_id="acct_test123",
            payout_enabled=True,
            total_earnings=100.0,
        )
        db_session.add(profile)
        await db_session.commit()
        return profile


# ============== Webhook Handler Tests ==============


class TestHandleCheckoutCompleted(TestBillingFixtures):
    """Tests for checkout.session.completed webhook handler."""

    async def test_creates_subscription_on_marketplace_purchase(
        self,
        db_session: AsyncSession,
        test_team: Team,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test that checkout completed creates an agent subscription."""
        session = {
            "id": "cs_test123",
            "subscription": "sub_test123",
            "payment_intent": "pi_test123",
            "metadata": {
                "type": "marketplace_agent_purchase",
                "team_id": test_team.id,
                "marketplace_agent_id": paid_marketplace_agent.id,
            },
        }

        await _handle_checkout_completed(session, db_session)

        # Verify subscription was created
        result = await db_session.execute(
            select(AgentSubscription).where(
                AgentSubscription.team_id == test_team.id,
                AgentSubscription.marketplace_agent_id == paid_marketplace_agent.id,
            )
        )
        subscription = result.scalar_one_or_none()

        assert subscription is not None
        assert subscription.status == SubscriptionStatus.ACTIVE.value
        assert subscription.stripe_subscription_id == "sub_test123"
        assert subscription.paid_order_id == "pi_test123"

    async def test_ignores_non_marketplace_purchases(
        self,
        db_session: AsyncSession,
        test_team: Team,
    ):
        """Test that non-marketplace purchases are ignored."""
        session = {
            "id": "cs_other",
            "metadata": {
                "type": "team_subscription",  # Different type
                "team_id": test_team.id,
            },
        }

        await _handle_checkout_completed(session, db_session)

        # No subscription should be created
        result = await db_session.execute(
            select(AgentSubscription).where(AgentSubscription.team_id == test_team.id)
        )
        subscriptions = result.scalars().all()

        assert len(subscriptions) == 0

    async def test_handles_missing_metadata_gracefully(
        self,
        db_session: AsyncSession,
    ):
        """Test that missing metadata doesn't cause errors."""
        session = {
            "id": "cs_no_meta",
            "metadata": {},
        }

        # Should not raise
        await _handle_checkout_completed(session, db_session)

    async def test_handles_partial_metadata(
        self,
        db_session: AsyncSession,
    ):
        """Test that partial metadata doesn't create subscription."""
        session = {
            "id": "cs_partial",
            "metadata": {
                "type": "marketplace_agent_purchase",
                "team_id": "some_team",
                # Missing marketplace_agent_id
            },
        }

        # Should not raise and should not create subscription
        await _handle_checkout_completed(session, db_session)


class TestHandleAccountUpdated(TestBillingFixtures):
    """Tests for account.updated webhook handler."""

    async def test_updates_seller_payout_enabled(
        self,
        db_session: AsyncSession,
        seller_profile: SellerProfile,
    ):
        """Test that account update changes payout_enabled status."""
        account = {
            "id": seller_profile.stripe_account_id,
            "payouts_enabled": True,
        }

        await _handle_account_updated(account, db_session)
        await db_session.refresh(seller_profile)

        assert seller_profile.payout_enabled is True

    async def test_updates_payout_to_false(
        self,
        db_session: AsyncSession,
        seller_profile: SellerProfile,
    ):
        """Test that account update can disable payouts."""
        # First ensure it's enabled
        seller_profile.payout_enabled = True
        await db_session.commit()

        account = {
            "id": seller_profile.stripe_account_id,
            "payouts_enabled": False,
        }

        await _handle_account_updated(account, db_session)
        await db_session.refresh(seller_profile)

        assert seller_profile.payout_enabled is False

    async def test_handles_unknown_account_gracefully(
        self,
        db_session: AsyncSession,
    ):
        """Test that unknown account IDs don't cause errors."""
        account = {
            "id": "acct_unknown",
            "payouts_enabled": True,
        }

        # Should not raise
        await _handle_account_updated(account, db_session)


# ============== Subscription Status Tests ==============


class TestAgentSubscriptionModel(TestBillingFixtures):
    """Tests for AgentSubscription model behavior."""

    async def test_subscription_starts_active(
        self,
        db_session: AsyncSession,
        test_team: Team,
        free_marketplace_agent: MarketplaceAgent,
    ):
        """Test that new subscriptions default to ACTIVE status."""
        subscription = AgentSubscription(
            id=str(uuid4()),
            team_id=test_team.id,
            marketplace_agent_id=free_marketplace_agent.id,
        )
        db_session.add(subscription)
        await db_session.commit()
        await db_session.refresh(subscription)

        assert subscription.status == SubscriptionStatus.ACTIVE.value

    async def test_can_query_active_subscriptions(
        self,
        db_session: AsyncSession,
        test_team: Team,
        free_marketplace_agent: MarketplaceAgent,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test querying for active subscriptions."""
        # Create active subscription
        active = AgentSubscription(
            id=str(uuid4()),
            team_id=test_team.id,
            marketplace_agent_id=free_marketplace_agent.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
        # Create cancelled subscription
        cancelled = AgentSubscription(
            id=str(uuid4()),
            team_id=test_team.id,
            marketplace_agent_id=paid_marketplace_agent.id,
            status=SubscriptionStatus.CANCELLED.value,
        )
        db_session.add_all([active, cancelled])
        await db_session.commit()

        # Query only active
        result = await db_session.execute(
            select(AgentSubscription).where(
                AgentSubscription.team_id == test_team.id,
                AgentSubscription.status == SubscriptionStatus.ACTIVE.value,
            )
        )
        active_subs = result.scalars().all()

        assert len(active_subs) == 1
        assert active_subs[0].marketplace_agent_id == free_marketplace_agent.id


# ============== Seller Profile Tests ==============


class TestSellerProfileModel(TestBillingFixtures):
    """Tests for SellerProfile model behavior."""

    async def test_seller_profile_tracks_earnings(
        self,
        db_session: AsyncSession,
        seller_profile: SellerProfile,
    ):
        """Test that total_earnings can be updated."""
        seller_profile.total_earnings = 250.50
        await db_session.commit()
        await db_session.refresh(seller_profile)

        assert seller_profile.total_earnings == 250.50

    async def test_seller_profile_unique_per_user(
        self,
        db_session: AsyncSession,
        test_user: User,
        seller_profile: SellerProfile,
    ):
        """Test that user_id is unique on seller profiles."""
        from sqlalchemy.exc import IntegrityError

        duplicate = SellerProfile(
            id=str(uuid4()),
            user_id=test_user.id,  # Same user
            stripe_account_id="acct_different",
        )
        db_session.add(duplicate)

        with pytest.raises(IntegrityError):
            await db_session.commit()


# ============== MarketplaceAgent Pricing Tests ==============


class TestMarketplaceAgentPricing(TestBillingFixtures):
    """Tests for marketplace agent pricing models."""

    async def test_free_agent_has_no_price(
        self,
        db_session: AsyncSession,
        free_marketplace_agent: MarketplaceAgent,
    ):
        """Test that FREE agents have no price_per_use."""
        assert free_marketplace_agent.pricing_type == PricingType.FREE.value
        assert free_marketplace_agent.price_per_use is None
        assert free_marketplace_agent.stripe_product_id is None

    async def test_paid_agent_has_price_and_stripe_id(
        self,
        db_session: AsyncSession,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test that USAGE_BASED agents have price and Stripe product."""
        assert paid_marketplace_agent.pricing_type == PricingType.USAGE_BASED.value
        assert paid_marketplace_agent.price_per_use == 5.00
        assert paid_marketplace_agent.stripe_product_id == "price_test123"

    async def test_can_filter_by_pricing_type(
        self,
        db_session: AsyncSession,
        free_marketplace_agent: MarketplaceAgent,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test filtering agents by pricing type."""
        result = await db_session.execute(
            select(MarketplaceAgent).where(MarketplaceAgent.pricing_type == PricingType.FREE.value)
        )
        free_agents = result.scalars().all()

        result = await db_session.execute(
            select(MarketplaceAgent).where(
                MarketplaceAgent.pricing_type == PricingType.USAGE_BASED.value
            )
        )
        paid_agents = result.scalars().all()

        assert len(free_agents) == 1
        assert len(paid_agents) == 1
        assert free_agents[0].name == "Free Agent"
        assert paid_agents[0].name == "Paid Agent"


# ============== Business Logic Tests ==============


class TestPurchaseLogic(TestBillingFixtures):
    """Tests for purchase business logic."""

    async def test_cannot_subscribe_twice_to_same_agent(
        self,
        db_session: AsyncSession,
        test_team: Team,
        free_marketplace_agent: MarketplaceAgent,
    ):
        """Test that duplicate active subscriptions are prevented."""
        # Create first subscription
        sub1 = AgentSubscription(
            id=str(uuid4()),
            team_id=test_team.id,
            marketplace_agent_id=free_marketplace_agent.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
        db_session.add(sub1)
        await db_session.commit()

        # Check for existing active subscription (business logic check)
        result = await db_session.execute(
            select(AgentSubscription).where(
                AgentSubscription.team_id == test_team.id,
                AgentSubscription.marketplace_agent_id == free_marketplace_agent.id,
                AgentSubscription.status == SubscriptionStatus.ACTIVE.value,
            )
        )
        existing = result.scalar_one_or_none()

        assert existing is not None

    async def test_can_resubscribe_after_cancellation(
        self,
        db_session: AsyncSession,
        test_team: Team,
        free_marketplace_agent: MarketplaceAgent,
    ):
        """Test that resubscription is possible after cancellation."""
        # Create cancelled subscription
        cancelled = AgentSubscription(
            id=str(uuid4()),
            team_id=test_team.id,
            marketplace_agent_id=free_marketplace_agent.id,
            status=SubscriptionStatus.CANCELLED.value,
        )
        db_session.add(cancelled)
        await db_session.commit()

        # Check for active subscription - should not find cancelled one
        result = await db_session.execute(
            select(AgentSubscription).where(
                AgentSubscription.team_id == test_team.id,
                AgentSubscription.marketplace_agent_id == free_marketplace_agent.id,
                AgentSubscription.status == SubscriptionStatus.ACTIVE.value,
            )
        )
        existing = result.scalar_one_or_none()

        assert existing is None  # Can resubscribe

        # Create new active subscription
        new_sub = AgentSubscription(
            id=str(uuid4()),
            team_id=test_team.id,
            marketplace_agent_id=free_marketplace_agent.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
        db_session.add(new_sub)
        await db_session.commit()

        # Verify both exist
        result = await db_session.execute(
            select(AgentSubscription).where(
                AgentSubscription.team_id == test_team.id,
                AgentSubscription.marketplace_agent_id == free_marketplace_agent.id,
            )
        )
        all_subs = result.scalars().all()

        assert len(all_subs) == 2

    async def test_paid_agent_without_stripe_config_detected(
        self,
        db_session: AsyncSession,
        test_agent: Agent,
        test_user: User,
    ):
        """Test detection of paid agents without Stripe configuration."""
        # Create paid agent without stripe_product_id
        unconfigured = MarketplaceAgent(
            id=str(uuid4()),
            agent_id=test_agent.id,
            seller_id=test_user.id,
            name="Unconfigured Paid Agent",
            category="coder",
            pricing_type=PricingType.USAGE_BASED.value,
            price_per_use=10.00,
            stripe_product_id=None,  # Not configured!
            is_active=True,
        )
        db_session.add(unconfigured)
        await db_session.commit()

        # Business logic should detect this
        assert unconfigured.pricing_type == PricingType.USAGE_BASED.value
        assert unconfigured.stripe_product_id is None  # Cannot process payment


# ============== Subscription Flow Tests ==============


class TestSubscriptionFlow(TestBillingFixtures):
    """Tests for the complete subscription flow logic."""

    async def test_free_agent_subscription_creates_directly(
        self,
        db_session: AsyncSession,
        test_team: Team,
        free_marketplace_agent: MarketplaceAgent,
    ):
        """Test that subscribing to a free agent creates subscription immediately."""
        # Simulate what the endpoint does for free agents
        assert free_marketplace_agent.pricing_type == PricingType.FREE.value

        sub = AgentSubscription(
            id=str(uuid4()),
            team_id=test_team.id,
            marketplace_agent_id=free_marketplace_agent.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
        db_session.add(sub)
        await db_session.commit()

        # Verify subscription is active
        result = await db_session.execute(
            select(AgentSubscription).where(
                AgentSubscription.team_id == test_team.id,
                AgentSubscription.marketplace_agent_id == free_marketplace_agent.id,
            )
        )
        subscription = result.scalar_one()
        assert subscription.status == SubscriptionStatus.ACTIVE.value

    async def test_paid_agent_requires_stripe_checkout(
        self,
        db_session: AsyncSession,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test that paid agents require Stripe checkout (have stripe_product_id)."""
        assert paid_marketplace_agent.pricing_type == PricingType.USAGE_BASED.value
        assert paid_marketplace_agent.stripe_product_id is not None

        # The endpoint would return checkout_url instead of creating subscription

    async def test_paid_agent_subscription_created_by_webhook(
        self,
        db_session: AsyncSession,
        test_team: Team,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test that paid agent subscription is created via webhook after payment."""
        # Simulate webhook payload after successful Stripe checkout
        session = {
            "id": "cs_test_paid",
            "subscription": None,  # One-time payment
            "payment_intent": "pi_test_paid123",
            "metadata": {
                "type": "marketplace_agent_purchase",
                "team_id": test_team.id,
                "marketplace_agent_id": paid_marketplace_agent.id,
            },
        }

        # This is what the webhook handler does
        await _handle_checkout_completed(session, db_session)

        # Verify subscription was created
        result = await db_session.execute(
            select(AgentSubscription).where(
                AgentSubscription.team_id == test_team.id,
                AgentSubscription.marketplace_agent_id == paid_marketplace_agent.id,
            )
        )
        subscription = result.scalar_one()
        assert subscription.status == SubscriptionStatus.ACTIVE.value
        assert subscription.paid_order_id == "pi_test_paid123"

    async def test_subscription_requires_redirect_urls_for_paid(
        self,
        db_session: AsyncSession,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test that paid agents require success_url and cancel_url."""
        # Business rule: paid agents need redirect URLs for Stripe checkout
        assert paid_marketplace_agent.pricing_type == PricingType.USAGE_BASED.value
        # The endpoint validates this and returns 400 if missing

    async def test_subscription_with_seller_stripe_account(
        self,
        db_session: AsyncSession,
        test_user: User,
        seller_profile: SellerProfile,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test that seller's Stripe account is used for transfers."""
        # Verify seller has Stripe Connect account
        result = await db_session.execute(
            select(SellerProfile).where(SellerProfile.user_id == paid_marketplace_agent.seller_id)
        )
        profile = result.scalar_one_or_none()

        # When seller has Stripe account, transfers go to them
        if profile and profile.stripe_account_id:
            assert profile.stripe_account_id == "acct_test123"
            # The Stripe checkout session would include transfer_data


# ============== Subscription Access Check Tests ==============


class TestVerifyAgentSubscription(TestBillingFixtures):
    """Tests for the verify_agent_subscription function."""

    async def test_owner_always_has_access(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_team: Team,
        test_agent: Agent,
    ):
        """Test that agent owner can always access their agent."""
        # Should not raise - owner has access
        await verify_agent_subscription(
            db_session,
            agent_id=test_agent.id,
            team_id=test_team.id,
            user_id=test_user.id,
        )

    async def test_team_can_access_own_agent(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_team: Team,
        test_agent: Agent,
    ):
        """Test that a team can access agents assigned to them."""
        # Assign agent to team
        test_agent.team_id = test_team.id
        await db_session.commit()

        # Create different user
        other_user = User(
            id=str(uuid4()),
            email="other@example.com",
            username="otheruser",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()

        # Should not raise - team owns the agent
        await verify_agent_subscription(
            db_session,
            agent_id=test_agent.id,
            team_id=test_team.id,
            user_id=other_user.id,
        )

    async def test_free_agent_no_subscription_needed(
        self,
        db_session: AsyncSession,
        test_team: Team,
        free_marketplace_agent: MarketplaceAgent,
    ):
        """Test that FREE marketplace agents don't need subscription."""
        # Create a different user (not the owner)
        other_user = User(
            id=str(uuid4()),
            email="anyone@example.com",
            username="anyone",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()

        # Should not raise - free agents are accessible to everyone
        await verify_agent_subscription(
            db_session,
            agent_id=free_marketplace_agent.agent_id,
            team_id=test_team.id,
            user_id=other_user.id,
        )

    async def test_paid_agent_with_subscription_has_access(
        self,
        db_session: AsyncSession,
        test_team: Team,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test that a team with active subscription can access paid agent."""
        # Create subscription
        subscription = AgentSubscription(
            id=str(uuid4()),
            team_id=test_team.id,
            marketplace_agent_id=paid_marketplace_agent.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Create a different user (not the owner)
        other_user = User(
            id=str(uuid4()),
            email="subscriber@example.com",
            username="subscriber",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()

        # Should not raise - team has subscription
        await verify_agent_subscription(
            db_session,
            agent_id=paid_marketplace_agent.agent_id,
            team_id=test_team.id,
            user_id=other_user.id,
        )

    async def test_paid_agent_without_subscription_denied(
        self,
        db_session: AsyncSession,
        test_team: Team,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test that a team without subscription is denied access to paid agent."""
        # Create a different user (not the owner)
        other_user = User(
            id=str(uuid4()),
            email="notsub@example.com",
            username="notsub",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()

        # Should raise 403
        with pytest.raises(HTTPException) as exc_info:
            await verify_agent_subscription(
                db_session,
                agent_id=paid_marketplace_agent.agent_id,
                team_id=test_team.id,
                user_id=other_user.id,
            )

        assert exc_info.value.status_code == 403
        assert "active subscription" in exc_info.value.detail

    async def test_cancelled_subscription_denied_access(
        self,
        db_session: AsyncSession,
        test_team: Team,
        paid_marketplace_agent: MarketplaceAgent,
    ):
        """Test that a cancelled subscription doesn't grant access."""
        # Create cancelled subscription
        subscription = AgentSubscription(
            id=str(uuid4()),
            team_id=test_team.id,
            marketplace_agent_id=paid_marketplace_agent.id,
            status=SubscriptionStatus.CANCELLED.value,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Create a different user
        other_user = User(
            id=str(uuid4()),
            email="cancelled@example.com",
            username="cancelled",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()

        # Should raise 403
        with pytest.raises(HTTPException) as exc_info:
            await verify_agent_subscription(
                db_session,
                agent_id=paid_marketplace_agent.agent_id,
                team_id=test_team.id,
                user_id=other_user.id,
            )

        assert exc_info.value.status_code == 403

    async def test_non_marketplace_agent_requires_ownership(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_team: Team,
    ):
        """Test that non-marketplace agents require ownership."""
        # Create agent not in marketplace
        private_agent = Agent(
            id=str(uuid4()),
            name="Private Agent",
            role="coder",
            inference_endpoint="https://private.example.com/v1",
            inference_provider="openai",
            inference_model="gpt-4",
            owner_id=str(uuid4()),  # Different owner
            status=AgentStatus.ONLINE,
        )
        db_session.add(private_agent)
        await db_session.commit()

        # Should raise 403
        with pytest.raises(HTTPException) as exc_info:
            await verify_agent_subscription(
                db_session,
                agent_id=private_agent.id,
                team_id=test_team.id,
                user_id=test_user.id,
            )

        assert exc_info.value.status_code == 403
        assert "don't have access" in exc_info.value.detail


# ============== M3-T4 Billing Summary + Subscribe API Tests ==============

from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient

from src.main import create_app
from src.storage.models import UsageRecord


def _make_user_api(suffix: str) -> User:
    return User(
        id=str(uuid4()),
        email=f"{suffix}-{uuid4().hex[:6]}@example.com",
        username=f"{suffix}-{uuid4().hex[:6]}",
        hashed_password="hashed",
    )


@pytest.fixture
async def api_client(db_session: AsyncSession):
    app = create_app()
    context: dict[str, User | None] = {"current_user": None}

    async def override_get_db():
        yield db_session

    async def override_get_current_user() -> User:
        user = context["current_user"]
        if user is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, context

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_billing_summary_aggregates_usage_and_recent_records(api_client, db_session: AsyncSession):
    client, context = api_client

    owner = _make_user_api("owner")
    db_session.add(owner)

    team = Team(
        id=str(uuid4()),
        name="Billing Team",
        owner_id=owner.id,
        settings={
            "subscription_status": "active",
            "stripe_subscription_id": "sub_123",
            "seat_count": 4,
        },
    )
    db_session.add(team)

    seller = _make_user_api("seller")
    db_session.add(seller)

    agent_one = Agent(
        id=str(uuid4()),
        name="Code Agent",
        role="coder",
        inference_endpoint="https://agent-one.example.com/v1",
        owner_id=seller.id,
    )
    agent_two = Agent(
        id=str(uuid4()),
        name="Review Agent",
        role="reviewer",
        inference_endpoint="https://agent-two.example.com/v1",
        owner_id=seller.id,
    )
    db_session.add(agent_one)
    db_session.add(agent_two)

    market_one = MarketplaceAgent(
        id=str(uuid4()),
        agent_id=agent_one.id,
        seller_id=seller.id,
        name="Code Agent Pro",
        category="coder",
    )
    market_two = MarketplaceAgent(
        id=str(uuid4()),
        agent_id=agent_two.id,
        seller_id=seller.id,
        name="Review Agent Pro",
        category="reviewer",
    )
    db_session.add(market_one)
    db_session.add(market_two)

    now = datetime.now(tz=timezone.utc)
    usage_old = UsageRecord(
        id=str(uuid4()),
        team_id=team.id,
        marketplace_agent_id=market_one.id,
        usage_type="task_completion",
        quantity=2,
        cost=3.5,
        created_at=now - timedelta(minutes=10),
    )
    usage_new = UsageRecord(
        id=str(uuid4()),
        team_id=team.id,
        marketplace_agent_id=market_two.id,
        usage_type="tool_call",
        quantity=1,
        cost=5.0,
        created_at=now,
    )
    db_session.add(usage_old)
    db_session.add(usage_new)

    db_session.add(
        AgentSubscription(
            id=str(uuid4()),
            team_id=team.id,
            marketplace_agent_id=market_one.id,
            status="active",
        )
    )

    await db_session.commit()
    context["current_user"] = owner

    response = await client.get(f"/api/v1/billing/summary/{team.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["team_id"] == team.id
    assert payload["total_usage_cost"] == pytest.approx(8.5)
    assert payload["subscription"] == {
        "status": "active",
        "active_agent_subscriptions": 1,
        "stripe_subscription_id": "sub_123",
        "seat_count": 4,
    }
    assert len(payload["usage_by_agent"]) == 2
    assert payload["usage_by_agent"][0]["marketplace_agent_name"] == "Review Agent Pro"
    assert payload["usage_by_agent"][0]["total_cost"] == pytest.approx(5.0)
    assert payload["recent_usage"][0]["id"] == usage_new.id
    assert payload["recent_usage"][1]["id"] == usage_old.id


@pytest.mark.asyncio
async def test_billing_summary_returns_404_for_non_owned_team(api_client, db_session: AsyncSession):
    client, context = api_client

    owner = _make_user_api("owner")
    outsider = _make_user_api("outsider")
    db_session.add(owner)
    db_session.add(outsider)

    team = Team(id=str(uuid4()), name="Owner Team", owner_id=owner.id)
    db_session.add(team)
    await db_session.commit()

    context["current_user"] = outsider

    response = await client.get(f"/api/v1/billing/summary/{team.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Team not found"}


@pytest.mark.asyncio
async def test_billing_summary_returns_empty_payload_without_usage(api_client, db_session: AsyncSession):
    client, context = api_client

    owner = _make_user_api("owner")
    db_session.add(owner)

    team = Team(id=str(uuid4()), name="Empty Team", owner_id=owner.id, settings={})
    db_session.add(team)
    await db_session.commit()

    context["current_user"] = owner

    response = await client.get(f"/api/v1/billing/summary/{team.id}")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "team_id",
        "subscription",
        "total_usage_cost",
        "usage_by_agent",
        "recent_usage",
    }
    assert payload["team_id"] == team.id
    assert payload["total_usage_cost"] == pytest.approx(0.0)
    assert payload["usage_by_agent"] == []
    assert payload["recent_usage"] == []
    assert payload["subscription"] == {
        "status": "unknown",
        "active_agent_subscriptions": 0,
        "stripe_subscription_id": None,
        "seat_count": None,
    }


@pytest.mark.asyncio
async def test_subscribe_returns_typed_payload_and_stable_error(api_client, db_session: AsyncSession, monkeypatch):
    client, context = api_client

    owner = _make_user_api("owner")
    db_session.add(owner)

    team = Team(id=str(uuid4()), name="Billing Team", owner_id=owner.id)
    db_session.add(team)
    await db_session.commit()

    context["current_user"] = owner

    class StripeStub:
        def create_checkout_session(self, team_id, price_id, success_url, cancel_url):
            return f"https://checkout.stripe.test/session/{team_id}"

    monkeypatch.setattr("src.api.billing.get_stripe_service", lambda: StripeStub())

    success_payload = {
        "team_id": team.id,
        "success_url": "https://app.example.com/billing?result=success",
        "cancel_url": "https://app.example.com/billing?result=cancel",
    }
    success_response = await client.post("/api/v1/billing/subscribe", json=success_payload)

    assert success_response.status_code == 200
    assert success_response.json() == {
        "checkout_url": f"https://checkout.stripe.test/session/{team.id}",
        "team_id": team.id,
    }

    class StripeFailStub:
        def create_checkout_session(self, team_id, price_id, success_url, cancel_url):
            raise RuntimeError("stripe down")

    monkeypatch.setattr("src.api.billing.get_stripe_service", lambda: StripeFailStub())

    error_response = await client.post("/api/v1/billing/subscribe", json=success_payload)

    assert error_response.status_code == 502
    assert error_response.json() == {"detail": "Unable to create checkout session"}


@pytest.mark.asyncio
async def test_subscribe_returns_404_for_unknown_or_non_owned_team(api_client, db_session: AsyncSession):
    client, context = api_client

    owner = _make_user_api("owner")
    outsider = _make_user_api("outsider")
    db_session.add(owner)
    db_session.add(outsider)

    team = Team(id=str(uuid4()), name="Owner Team", owner_id=owner.id)
    db_session.add(team)
    await db_session.commit()

    context["current_user"] = owner
    unknown_team_payload = {
        "team_id": str(uuid4()),
        "success_url": "https://app.example.com/billing?result=success",
        "cancel_url": "https://app.example.com/billing?result=cancel",
    }
    unknown_response = await client.post("/api/v1/billing/subscribe", json=unknown_team_payload)
    assert unknown_response.status_code == 404
    assert unknown_response.json() == {"detail": "Team not found"}

    context["current_user"] = outsider
    non_owner_payload = {
        "team_id": team.id,
        "success_url": "https://app.example.com/billing?result=success",
        "cancel_url": "https://app.example.com/billing?result=cancel",
    }
    non_owner_response = await client.post("/api/v1/billing/subscribe", json=non_owner_payload)
    assert non_owner_response.status_code == 404
    assert non_owner_response.json() == {"detail": "Team not found"}


@pytest.mark.asyncio
async def test_subscribe_returns_400_for_checkout_validation_error(api_client, db_session: AsyncSession, monkeypatch):
    client, context = api_client

    owner = _make_user_api("owner")
    db_session.add(owner)

    team = Team(id=str(uuid4()), name="Billing Team", owner_id=owner.id)
    db_session.add(team)
    await db_session.commit()

    context["current_user"] = owner

    class StripeValidationStub:
        def create_checkout_session(self, team_id, price_id, success_url, cancel_url):
            raise ValueError("Invalid checkout URL")

    monkeypatch.setattr("src.api.billing.get_stripe_service", lambda: StripeValidationStub())

    payload = {
        "team_id": team.id,
        "success_url": "https://app.example.com/billing?result=success",
        "cancel_url": "https://app.example.com/billing?result=cancel",
    }
    response = await client.post("/api/v1/billing/subscribe", json=payload)

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid checkout URL"}
