"""Seed script to populate agents, skills, and a demo team into the database."""

import asyncio
from uuid import uuid4
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import get_settings
from src.storage.models import Base, User, Team, TeamMember, Agent, MarketplaceAgent
from src.core.state import AgentStatus, PricingType, TeamRole
from src.api.auth import get_password_hash


async def seed_database():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
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

        team_id = str(uuid4())
        team = Team(
            id=team_id,
            name="Demo Team",
            slug="demo-team",
            description="A demo team for showcasing the platform",
            owner_id=demo_user_id,
        )
        session.add(team)

        team_member = TeamMember(
            id=str(uuid4()),
            team_id=team_id,
            user_id=demo_user_id,
            role=TeamRole.ADMIN.value,
        )
        session.add(team_member)

        default_agents = [
            {
                "name": "Senior Python Developer",
                "role": "coder",
                "description": "Expert in writing, refactoring, and debugging Python code. Specializes in FastAPI and LangGraph.",
                "category": "Development",
                "pricing_type": PricingType.FREE.value,
                "price": 0.0,
                "endpoint": "http://agent-coder:8000/mcp",
                "skills": [
                    "generate_code",
                    "write_file",
                    "search_code",
                    "read_file",
                    "list_directory",
                    "run_command",
                ],
            },
            {
                "name": "Security Reviewer",
                "role": "reviewer",
                "description": "Performs static analysis and checks for OWASP vulnerabilities in pull requests and subtasks.",
                "category": "Security",
                "pricing_type": PricingType.USAGE_BASED.value,
                "price": 0.05,
                "endpoint": "http://agent-reviewer:8000/mcp",
                "skills": ["review_code", "check_security", "suggest_improvements", "review_file"],
            },
            {
                "name": "Frontend Design Agent",
                "role": "designer",
                "description": "Generates React components, translates UI requirements into TailwindCSS.",
                "category": "Frontend",
                "pricing_type": PricingType.USAGE_BASED.value,
                "price": 0.10,
                "endpoint": "http://agent-designer:8000/mcp",
                "skills": [
                    "generate_code",
                    "suggest_improvements",
                    "write_file",
                    "read_file",
                    "analyze_component_structure",
                ],
            },
        ]

        print("Seeding Agents into Marketplace...")
        for agent_data in default_agents:
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
        print(f"Demo team created with ID: {team_id}")
        print(f"Demo PM user: demo_pm / demo123")


if __name__ == "__main__":
    asyncio.run(seed_database())
