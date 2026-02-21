"""Seed script to populate default agents and skills into the marketplace."""

import asyncio
from uuid import uuid4
import sys
import os

# Add src to path so we can import from backend correctly
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import get_settings
from src.storage.models import Base, User, Agent, MarketplaceAgent
from src.core.state import AgentStatus, PricingType
from src.api.auth import get_password_hash


async def seed_database():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # 1. Create a platform owner user
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

        # 2. Define Default Agents and their Skills (Capabilities)
        default_agents = [
            {
                "name": "Senior Python Developer",
                "role": "coder",
                "description": "Expert in writing, refactoring, and debugging Python code. Specializes in FastAPI and LangGraph.",
                "category": "Development",
                "pricing_type": PricingType.FREE.value,
                "price": 0.0,
                "endpoint": "http://localhost:8001/mcp",
                "skills": ["generate_code", "write_file", "search_code"],
            },
            {
                "name": "Security Reviewer",
                "role": "reviewer",
                "description": "Performs static analysis and checks for OWASP vulnerabilities in pull requests and subtasks.",
                "category": "Security",
                "pricing_type": PricingType.USAGE_BASED.value,
                "price": 0.05,  # $0.05 per tool call
                "endpoint": "http://localhost:8002/mcp",
                "skills": ["review_code", "check_security", "read_file"],
            },
            {
                "name": "Frontend Design Agent",
                "role": "designer",
                "description": "Generates Lovable React components, translates UI requirements into TailwindCSS.",
                "category": "Frontend",
                "pricing_type": PricingType.USAGE_BASED.value,
                "price": 0.10,
                "endpoint": "http://localhost:8003/mcp",
                "skills": ["generate_code", "suggest_improvements", "write_file"],
            },
        ]

        print("Seeding Agents into Marketplace...")
        for agent_data in default_agents:
            # Create base Agent
            agent_id = str(uuid4())
            agent = Agent(
                id=agent_id,
                name=agent_data["name"],
                role=agent_data["role"],
                description=agent_data["description"],
                mcp_endpoint=agent_data["endpoint"],
                owner_id=owner_id,
                status=AgentStatus.OFFLINE.value,
                extra_data={"expected_skills": agent_data["skills"]},
            )
            session.add(agent)

            # Create Marketplace Listing
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
        print(f"Successfully seeded {len(default_agents)} default agents into the marketplace!")


if __name__ == "__main__":
    asyncio.run(seed_database())
