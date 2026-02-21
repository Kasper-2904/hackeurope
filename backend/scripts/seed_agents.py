"""Seed script to populate agents and demo data."""

import asyncio
from uuid import uuid4
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import get_settings
from src.storage.models import Base, User, Team, Agent, MarketplaceAgent
from src.core.state import AgentStatus, PricingType
from src.api.auth import get_password_hash

# Get settings for default model
settings = get_settings()


async def seed_database():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Platform owner
        owner_id = str(uuid4())
        owner = User(
            id=owner_id,
            email="platform@unifai.com",
            username="unifai_admin",
            hashed_password=get_password_hash("adminpassword123"),
            full_name="Unifai Platform",
            is_active=True,
            is_superuser=True,
        )
        session.add(owner)

        # Demo user
        demo_user_id = str(uuid4())
        demo_user = User(
            id=demo_user_id,
            email="pm@demo.com",
            username="demo_pm",
            hashed_password=get_password_hash("demo123"),
            full_name="Demo PM",
            is_active=True,
            is_superuser=False,
        )
        session.add(demo_user)

        # Demo team
        team_id = str(uuid4())
        team = Team(
            id=team_id,
            name="Demo Team",
            description="A demo team for showcasing the platform",
            owner_id=demo_user_id,
        )
        session.add(team)

        # Extract model info from settings (e.g., "anthropic/claude-sonnet-4-20250514")
        default_model = settings.default_llm_model
        if "/" in default_model:
            inference_provider, inference_model = default_model.split("/", 1)
        else:
            inference_provider = "anthropic"
            inference_model = default_model

        # Marketplace agents (hosted by platform)
        default_agents = [
            {
                "name": "Senior Python Developer",
                "role": "coder",
                "description": "Expert in writing, refactoring, and debugging Python code. Specializes in FastAPI and backend development.",
                "inference_endpoint": "https://api.anthropic.com/v1",
                "inference_provider": inference_provider,
                "inference_model": inference_model,
                "system_prompt": "You are an expert Python developer. Help users write clean, efficient, and well-documented code.",
                "skills": [
                    "generate_code",
                    "review_code",
                    "debug_code",
                    "refactor_code",
                    "explain_code",
                ],
                "category": "Development",
                "pricing_type": PricingType.FREE.value,
                "price": 0.0,
            },
            {
                "name": "Security Reviewer",
                "role": "reviewer",
                "description": "Performs static analysis and checks for OWASP vulnerabilities in pull requests.",
                "inference_endpoint": "https://api.anthropic.com/v1",
                "inference_provider": inference_provider,
                "inference_model": inference_model,
                "system_prompt": "You are a security expert. Review code for vulnerabilities and suggest fixes.",
                "skills": ["review_code", "check_security", "suggest_improvements"],
                "category": "Security",
                "pricing_type": PricingType.USAGE_BASED.value,
                "price": 0.05,
            },
            {
                "name": "Frontend Designer",
                "role": "designer",
                "description": "Generates React components and translates UI requirements into TailwindCSS.",
                "inference_endpoint": "https://api.anthropic.com/v1",
                "inference_provider": inference_provider,
                "inference_model": inference_model,
                "system_prompt": "You are a frontend expert. Create modern, accessible React components with TailwindCSS.",
                "skills": ["generate_code", "design_component", "suggest_improvements"],
                "category": "Frontend",
                "pricing_type": PricingType.USAGE_BASED.value,
                "price": 0.10,
            },
        ]

        print("Seeding Agents...")
        for agent_data in default_agents:
            agent_id = str(uuid4())
            agent = Agent(
                id=agent_id,
                name=agent_data["name"],
                role=agent_data["role"],
                description=agent_data["description"],
                inference_endpoint=agent_data["inference_endpoint"],
                inference_provider=agent_data["inference_provider"],
                inference_model=agent_data["inference_model"],
                system_prompt=agent_data["system_prompt"],
                skills=agent_data["skills"],
                owner_id=owner_id,
                status=AgentStatus.ONLINE,
            )
            session.add(agent)

            # Marketplace listing
            market_agent = MarketplaceAgent(
                id=str(uuid4()),
                agent_id=agent_id,
                seller_id=owner_id,
                name=agent_data["name"],
                description=agent_data["description"],
                category=agent_data["category"],
                pricing_type=agent_data["pricing_type"],
                price_per_use=agent_data["price"],
                is_verified=True,
                is_active=True,
            )
            session.add(market_agent)

        await session.commit()
        print(f"Successfully seeded {len(default_agents)} agents!")
        print(f"Demo team: {team_id}")
        print(f"Demo PM user: demo_pm / demo123")


if __name__ == "__main__":
    asyncio.run(seed_database())
