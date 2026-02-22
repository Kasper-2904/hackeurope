"""Tests for marketplace service."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.marketplace_service import MarketplaceService, get_marketplace_service
from src.storage.models import Agent, MarketplaceAgent, SellerProfile, User
from src.core.state import PricingType, AgentStatus


# ============== Fixtures ==============


@pytest.fixture
def mock_user():
    """Create a mock user/seller."""
    return User(
        id=str(uuid4()),
        email="seller@example.com",
        username="seller",
        hashed_password="hashed",
        is_active=True,
    )


@pytest.fixture
def mock_seller_profile(mock_user):
    """Create a mock seller profile with Stripe Connect."""
    return SellerProfile(
        id=str(uuid4()),
        user_id=mock_user.id,
        stripe_account_id="acct_seller123",
        payout_enabled=True,
    )


# ============== Publish Agent Tests ==============


class TestPublishAgent:
    """Tests for publishing agents to the marketplace."""

    @pytest.mark.asyncio
    async def test_publish_free_agent_success(self, db_session: AsyncSession, mock_user):
        """Test publishing a free agent creates agent and listing."""
        db_session.add(mock_user)
        await db_session.commit()

        marketplace_agent = await MarketplaceService.publish_agent(
            db=db_session,
            seller_id=mock_user.id,
            name="Free Test Agent",
            category="coder",
            inference_endpoint="https://agent.example.com/v1",
            access_token="token123",
            description="A free test agent",
            pricing_type=PricingType.FREE,
        )

        assert marketplace_agent is not None
        assert marketplace_agent.name == "Free Test Agent"
        assert marketplace_agent.pricing_type == PricingType.FREE.value
        assert marketplace_agent.stripe_product_id is None
        assert marketplace_agent.is_active is True
        assert marketplace_agent.agent is not None
        assert marketplace_agent.agent.name == "Free Test Agent"

    @pytest.mark.asyncio
    async def test_publish_paid_agent_with_stripe(
        self, db_session: AsyncSession, mock_user, mock_seller_profile
    ):
        """Test publishing a paid agent creates Stripe product."""
        db_session.add(mock_user)
        db_session.add(mock_seller_profile)
        await db_session.commit()

        mock_product_id = "prod_test123"
        mock_price_id = "price_test123"

        with patch("src.services.marketplace_service.get_stripe_service") as mock_stripe:
            mock_stripe_instance = MagicMock()
            mock_stripe_instance.create_product_and_price.return_value = (
                mock_product_id,
                mock_price_id,
            )
            mock_stripe.return_value = mock_stripe_instance

            marketplace_agent = await MarketplaceService.publish_agent(
                db=db_session,
                seller_id=mock_user.id,
                name="Paid Test Agent",
                category="reviewer",
                inference_endpoint="https://paid-agent.example.com/v1",
                access_token="token456",
                description="A paid test agent",
                pricing_type=PricingType.USAGE_BASED,
                price_per_use=5.00,
            )

        assert marketplace_agent.pricing_type == PricingType.USAGE_BASED.value
        assert marketplace_agent.price_per_use == 5.00
        assert marketplace_agent.stripe_product_id == mock_price_id

    @pytest.mark.asyncio
    async def test_publish_paid_agent_stripe_failure_still_creates(
        self, db_session: AsyncSession, mock_user
    ):
        """Test paid agent is created even if Stripe product creation fails."""
        db_session.add(mock_user)
        await db_session.commit()

        with patch("src.services.marketplace_service.get_stripe_service") as mock_stripe:
            mock_stripe_instance = MagicMock()
            mock_stripe_instance.create_product_and_price.side_effect = Exception(
                "Stripe API Error"
            )
            mock_stripe.return_value = mock_stripe_instance

            marketplace_agent = await MarketplaceService.publish_agent(
                db=db_session,
                seller_id=mock_user.id,
                name="Paid Agent No Stripe",
                category="coder",
                inference_endpoint="https://agent.example.com/v1",
                access_token="token789",
                pricing_type=PricingType.USAGE_BASED,
                price_per_use=10.00,
            )

        # Agent is still created but without stripe_product_id
        assert marketplace_agent is not None
        assert marketplace_agent.stripe_product_id is None

    @pytest.mark.asyncio
    async def test_publish_agent_creates_underlying_agent(
        self, db_session: AsyncSession, mock_user
    ):
        """Test that publishing creates both Agent and MarketplaceAgent records."""
        db_session.add(mock_user)
        await db_session.commit()

        marketplace_agent = await MarketplaceService.publish_agent(
            db=db_session,
            seller_id=mock_user.id,
            name="Agent With Skills",
            category="designer",
            inference_endpoint="https://designer.example.com/v1",
            access_token="design_token",
            inference_provider="anthropic",
            inference_model="claude-3",
            system_prompt="You are a design expert",
            skills=["figma", "ui_design", "prototyping"],
        )

        # Check underlying agent
        agent = marketplace_agent.agent
        assert agent is not None
        assert agent.name == "Agent With Skills"
        assert agent.role == "custom"  # Seller-hosted agents are custom role
        assert agent.inference_endpoint == "https://designer.example.com/v1"
        assert agent.inference_provider == "anthropic"
        assert agent.inference_model == "claude-3"
        assert agent.system_prompt == "You are a design expert"
        assert agent.skills == ["figma", "ui_design", "prototyping"]
        assert agent.owner_id == mock_user.id
        assert agent.status == AgentStatus.ONLINE

    @pytest.mark.asyncio
    async def test_publish_agent_without_seller_stripe_account(
        self, db_session: AsyncSession, mock_user
    ):
        """Test publishing paid agent when seller has no Stripe Connect account."""
        db_session.add(mock_user)
        # No seller profile added
        await db_session.commit()

        mock_product_id = "prod_no_seller"
        mock_price_id = "price_no_seller"

        with patch("src.services.marketplace_service.get_stripe_service") as mock_stripe:
            mock_stripe_instance = MagicMock()
            mock_stripe_instance.create_product_and_price.return_value = (
                mock_product_id,
                mock_price_id,
            )
            mock_stripe.return_value = mock_stripe_instance

            marketplace_agent = await MarketplaceService.publish_agent(
                db=db_session,
                seller_id=mock_user.id,
                name="No Seller Connect",
                category="coder",
                inference_endpoint="https://agent.example.com/v1",
                access_token="token",
                pricing_type=PricingType.USAGE_BASED,
                price_per_use=3.00,
            )

            # Verify create_product_and_price was called with None for seller account
            mock_stripe_instance.create_product_and_price.assert_called_once()
            call_args = mock_stripe_instance.create_product_and_price.call_args
            assert call_args.kwargs.get("seller_stripe_account_id") is None

        assert marketplace_agent.stripe_product_id == mock_price_id


# ============== List Public Agents Tests ==============


class TestListPublicAgents:
    """Tests for listing marketplace agents."""

    @pytest.mark.asyncio
    async def test_list_all_active_agents(self, db_session: AsyncSession, mock_user):
        """Test listing all active agents."""
        db_session.add(mock_user)
        await db_session.commit()

        # Create multiple agents
        for i in range(3):
            await MarketplaceService.publish_agent(
                db=db_session,
                seller_id=mock_user.id,
                name=f"Agent {i}",
                category="coder",
                inference_endpoint=f"https://agent{i}.example.com/v1",
                access_token=f"token{i}",
            )

        agents = await MarketplaceService.list_public_agents(db_session)

        assert len(agents) == 3

    @pytest.mark.asyncio
    async def test_list_agents_by_category(self, db_session: AsyncSession, mock_user):
        """Test filtering agents by category."""
        db_session.add(mock_user)
        await db_session.commit()

        # Create agents in different categories
        await MarketplaceService.publish_agent(
            db=db_session,
            seller_id=mock_user.id,
            name="Coder Agent",
            category="coder",
            inference_endpoint="https://coder.example.com/v1",
            access_token="coder_token",
        )
        await MarketplaceService.publish_agent(
            db=db_session,
            seller_id=mock_user.id,
            name="Reviewer Agent",
            category="reviewer",
            inference_endpoint="https://reviewer.example.com/v1",
            access_token="reviewer_token",
        )
        await MarketplaceService.publish_agent(
            db=db_session,
            seller_id=mock_user.id,
            name="Another Coder",
            category="coder",
            inference_endpoint="https://coder2.example.com/v1",
            access_token="coder2_token",
        )

        coder_agents = await MarketplaceService.list_public_agents(db_session, category="coder")
        reviewer_agents = await MarketplaceService.list_public_agents(
            db_session, category="reviewer"
        )

        assert len(coder_agents) == 2
        assert len(reviewer_agents) == 1
        assert all(a.category == "coder" for a in coder_agents)
        assert reviewer_agents[0].category == "reviewer"

    @pytest.mark.asyncio
    async def test_list_agents_excludes_inactive(self, db_session: AsyncSession, mock_user):
        """Test that inactive agents are not listed."""
        db_session.add(mock_user)
        await db_session.commit()

        # Create active agent
        await MarketplaceService.publish_agent(
            db=db_session,
            seller_id=mock_user.id,
            name="Active Agent",
            category="coder",
            inference_endpoint="https://active.example.com/v1",
            access_token="active_token",
        )

        # Create and deactivate agent
        inactive = await MarketplaceService.publish_agent(
            db=db_session,
            seller_id=mock_user.id,
            name="Inactive Agent",
            category="coder",
            inference_endpoint="https://inactive.example.com/v1",
            access_token="inactive_token",
        )
        inactive.is_active = False
        await db_session.commit()

        agents = await MarketplaceService.list_public_agents(db_session)

        assert len(agents) == 1
        assert agents[0].name == "Active Agent"


# ============== Get Marketplace Agent Tests ==============


class TestGetMarketplaceAgent:
    """Tests for getting a single marketplace agent."""

    @pytest.mark.asyncio
    async def test_get_marketplace_agent_success(self, db_session: AsyncSession, mock_user):
        """Test getting a marketplace agent by ID."""
        db_session.add(mock_user)
        await db_session.commit()

        created = await MarketplaceService.publish_agent(
            db=db_session,
            seller_id=mock_user.id,
            name="Specific Agent",
            category="coder",
            inference_endpoint="https://specific.example.com/v1",
            access_token="specific_token",
            description="A specific agent for testing",
        )

        retrieved = await MarketplaceService.get_marketplace_agent(db_session, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Specific Agent"
        assert retrieved.description == "A specific agent for testing"
        assert retrieved.agent is not None

    @pytest.mark.asyncio
    async def test_get_marketplace_agent_not_found(self, db_session: AsyncSession):
        """Test getting non-existent marketplace agent returns None."""
        result = await MarketplaceService.get_marketplace_agent(db_session, "nonexistent-id")

        assert result is None


# ============== Service Singleton Tests ==============


class TestGetMarketplaceService:
    """Tests for the marketplace service getter."""

    def test_get_marketplace_service_returns_instance(self):
        """Test that get_marketplace_service returns a MarketplaceService instance."""
        service = get_marketplace_service()
        assert isinstance(service, MarketplaceService)
