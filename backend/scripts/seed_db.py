"""Seed script to populate agents and demo data."""

import asyncio
from uuid import uuid4
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import get_settings
from src.storage.models import (
    Base,
    User,
    Team,
    Agent,
    MarketplaceAgent,
    Project,
    TeamMember,
    Task,
    Plan,
    Subtask,
)
from src.core.state import (
    AgentStatus,
    PricingType,
    UserRole,
    TaskStatus,
    PlanStatus,
    SubtaskStatus,
)
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
        print("=" * 50)
        print("Seeding Database...")
        print("=" * 50)

        # ============== USERS ==============
        print("\n[1/7] Creating Users...")

        # Platform admin (superuser)
        admin_id = str(uuid4())
        admin = User(
            id=admin_id,
            email="admin@unifai.com",
            username="admin",
            hashed_password=get_password_hash("admin123"),
            full_name="Platform Admin",
            is_active=True,
            is_superuser=True,
        )
        session.add(admin)

        # PM User
        pm_id = str(uuid4())
        pm_user = User(
            id=pm_id,
            email="pm@demo.com",
            username="demo_pm",
            hashed_password=get_password_hash("demo123"),
            full_name="Alice PM",
            is_active=True,
            is_superuser=False,
        )
        session.add(pm_user)

        # Developer Users
        dev1_id = str(uuid4())
        dev1 = User(
            id=dev1_id,
            email="dev1@demo.com",
            username="dev_bob",
            hashed_password=get_password_hash("demo123"),
            full_name="Bob Developer",
            is_active=True,
            is_superuser=False,
        )
        session.add(dev1)

        dev2_id = str(uuid4())
        dev2 = User(
            id=dev2_id,
            email="dev2@demo.com",
            username="dev_charlie",
            hashed_password=get_password_hash("demo123"),
            full_name="Charlie Developer",
            is_active=True,
            is_superuser=False,
        )
        session.add(dev2)

        print(f"  Created 4 users (admin, pm, 2 developers)")

        # ============== TEAMS ==============
        print("\n[2/7] Creating Teams...")

        team_id = str(uuid4())
        team = Team(
            id=team_id,
            name="Demo Team",
            description="A demo team for showcasing the platform",
            owner_id=pm_id,
        )
        session.add(team)
        print(f"  Created team: Demo Team")

        # ============== PROJECTS ==============
        print("\n[3/7] Creating Projects...")

        project1_id = str(uuid4())
        project1 = Project(
            id=project1_id,
            name="E-Commerce Platform",
            description="Build a modern e-commerce platform with React frontend and FastAPI backend",
            owner_id=pm_id,
            goals=[
                "Launch MVP in 3 months",
                "Support 1000 concurrent users",
                "WCAG 2.1 AA compliance",
            ],
            github_repo="https://github.com/demo/ecommerce-platform",
        )
        session.add(project1)

        project2_id = str(uuid4())
        project2 = Project(
            id=project2_id,
            name="Internal Dashboard",
            description="Analytics dashboard for internal metrics and KPI tracking",
            owner_id=pm_id,
            goals=["Real-time data updates", "Role-based access control"],
            github_repo="https://github.com/demo/internal-dashboard",
        )
        session.add(project2)
        print(f"  Created 2 projects")

        # ============== TEAM MEMBERS (with roles) ==============
        print("\n[4/7] Creating Team Members with Roles...")

        # PM on Project 1
        tm1 = TeamMember(
            id=str(uuid4()),
            user_id=pm_id,
            project_id=project1_id,
            role=UserRole.PM.value,
            skills=["project_management", "requirements", "stakeholder_communication"],
            capacity=0.5,
        )
        session.add(tm1)

        # PM on Project 2
        tm2 = TeamMember(
            id=str(uuid4()),
            user_id=pm_id,
            project_id=project2_id,
            role=UserRole.PM.value,
            skills=["project_management", "requirements"],
            capacity=0.5,
        )
        session.add(tm2)

        # Dev1 on Project 1 as Developer
        tm3 = TeamMember(
            id=str(uuid4()),
            user_id=dev1_id,
            project_id=project1_id,
            role=UserRole.DEVELOPER.value,
            skills=["python", "fastapi", "postgresql", "docker"],
            capacity=1.0,
        )
        session.add(tm3)

        # Dev2 on Project 1 as Developer
        tm4 = TeamMember(
            id=str(uuid4()),
            user_id=dev2_id,
            project_id=project1_id,
            role=UserRole.DEVELOPER.value,
            skills=["react", "typescript", "tailwindcss"],
            capacity=1.0,
        )
        session.add(tm4)

        # Dev1 on Project 2 as Admin (lead dev)
        tm5 = TeamMember(
            id=str(uuid4()),
            user_id=dev1_id,
            project_id=project2_id,
            role=UserRole.ADMIN.value,
            skills=["python", "data_analysis", "sql"],
            capacity=0.5,
        )
        session.add(tm5)

        print(f"  Created 5 team memberships with roles (PM, ADMIN, DEVELOPER)")

        # ============== AGENTS ==============
        print("\n[5/7] Creating Agents (Seller-Hosted)...")

        # These represent seller-hosted agents with their own endpoints and access tokens
        # In production, sellers would provide their own endpoints and tokens
        default_agents = [
            {
                "name": "Senior Python Developer",
                "role": "coder",
                "description": "Expert in writing, refactoring, and debugging Python code. Specializes in FastAPI and backend development.",
                "inference_endpoint": "https://seller1-python-agent.example.com/v1",
                "access_token": "seller1_token_python_dev_abc123",
                "inference_provider": "openai-compatible",
                "inference_model": "gpt-4o",
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
                "inference_endpoint": "https://seller2-security-agent.example.com/v1",
                "access_token": "seller2_token_security_xyz789",
                "inference_provider": "openai-compatible",
                "inference_model": "gpt-4o",
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
                "inference_endpoint": "https://seller3-frontend-agent.example.com/v1",
                "access_token": "seller3_token_frontend_def456",
                "inference_provider": "openai-compatible",
                "inference_model": "gpt-4o",
                "system_prompt": "You are a frontend expert. Create modern, accessible React components with TailwindCSS.",
                "skills": ["generate_code", "design_component", "suggest_improvements"],
                "category": "Frontend",
                "pricing_type": PricingType.USAGE_BASED.value,
                "price": 0.10,
            },
            {
                "name": "Code Reviewer",
                "role": "reviewer",
                "description": "Thorough code reviewer focusing on best practices, patterns, and maintainability.",
                "inference_endpoint": "https://seller1-code-reviewer.example.com/v1",
                "access_token": "seller1_token_reviewer_ghi012",
                "inference_provider": "openai-compatible",
                "inference_model": "gpt-4o-mini",
                "system_prompt": "You are an expert code reviewer. Focus on code quality, best practices, and maintainability.",
                "skills": ["review_code", "suggest_improvements", "explain_code"],
                "category": "Quality",
                "pricing_type": PricingType.FREE.value,
                "price": 0.0,
            },
            {
                "name": "DevOps Engineer",
                "role": "coder",
                "description": "Expert in Docker, Kubernetes, CI/CD pipelines, and infrastructure as code.",
                "inference_endpoint": "https://seller4-devops-agent.example.com/v1",
                "access_token": "seller4_token_devops_jkl345",
                "inference_provider": "openai-compatible",
                "inference_model": "gpt-4o",
                "system_prompt": "You are a DevOps expert. Help with containerization, deployment, and infrastructure automation.",
                "skills": ["generate_code", "debug_code", "suggest_improvements"],
                "category": "DevOps",
                "pricing_type": PricingType.USAGE_BASED.value,
                "price": 0.08,
            },
        ]

        agent_ids = []
        for agent_data in default_agents:
            agent_id = str(uuid4())
            agent_ids.append(agent_id)

            # Create the agent with seller's endpoint and access token
            agent = Agent(
                id=agent_id,
                name=agent_data["name"],
                role=agent_data["role"],
                description=agent_data["description"],
                inference_endpoint=agent_data["inference_endpoint"],
                inference_api_key_encrypted=agent_data["access_token"],  # Seller's access token
                inference_provider=agent_data["inference_provider"],
                inference_model=agent_data["inference_model"],
                system_prompt=agent_data["system_prompt"],
                skills=agent_data["skills"],
                owner_id=admin_id,
                team_id=team_id,
                status=AgentStatus.ONLINE,
            )
            session.add(agent)

            # Marketplace listing
            market_agent = MarketplaceAgent(
                id=str(uuid4()),
                agent_id=agent_id,
                seller_id=admin_id,
                name=agent_data["name"],
                description=agent_data["description"],
                category=agent_data["category"],
                pricing_type=agent_data["pricing_type"],
                price_per_use=agent_data["price"],
                is_verified=True,
                is_active=True,
            )
            session.add(market_agent)

        print(f"  Created {len(default_agents)} seller-hosted agents with marketplace listings")

        # ============== TASKS ==============
        print("\n[6/7] Creating Tasks...")

        task1_id = str(uuid4())
        task1 = Task(
            id=task1_id,
            title="Implement User Authentication API",
            description="Create JWT-based authentication endpoints including login, register, refresh token, and logout.",
            task_type="code_generation",
            status=TaskStatus.COMPLETED,
            team_id=team_id,
            created_by_id=pm_id,
            assigned_agent_id=agent_ids[0],  # Python Developer
            progress=1.0,
        )
        session.add(task1)

        task2_id = str(uuid4())
        task2 = Task(
            id=task2_id,
            title="Build Product Catalog Component",
            description="Create a React component for displaying products with filtering, sorting, and pagination.",
            task_type="code_generation",
            status=TaskStatus.IN_PROGRESS,
            team_id=team_id,
            created_by_id=pm_id,
            assigned_agent_id=agent_ids[2],  # Frontend Designer
            progress=0.6,
        )
        session.add(task2)

        task3_id = str(uuid4())
        task3 = Task(
            id=task3_id,
            title="Security Audit: Payment Module",
            description="Review the payment processing code for security vulnerabilities and PCI compliance.",
            task_type="code_review",
            status=TaskStatus.PENDING,
            team_id=team_id,
            created_by_id=pm_id,
            assigned_agent_id=agent_ids[1],  # Security Reviewer
            progress=0.0,
        )
        session.add(task3)

        task4_id = str(uuid4())
        task4 = Task(
            id=task4_id,
            title="Setup CI/CD Pipeline",
            description="Configure GitHub Actions for automated testing, building, and deployment to staging.",
            task_type="code_generation",
            status=TaskStatus.ASSIGNED,
            team_id=team_id,
            created_by_id=pm_id,
            assigned_agent_id=agent_ids[4],  # DevOps Engineer
            progress=0.0,
        )
        session.add(task4)

        print(f"  Created 4 tasks with various statuses")

        # ============== PLANS ==============
        print("\n[7/7] Creating Plans and Subtasks...")

        # Plan for Task 2 (in progress)
        plan1_id = str(uuid4())
        plan1 = Plan(
            id=plan1_id,
            task_id=task2_id,
            project_id=project1_id,
            plan_data={
                "subtasks": [
                    {
                        "title": "Create ProductCard component",
                        "agent_type": "designer",
                        "priority": 1,
                    },
                    {"title": "Implement filtering logic", "agent_type": "coder", "priority": 2},
                    {"title": "Add pagination component", "agent_type": "designer", "priority": 3},
                    {"title": "Write unit tests", "agent_type": "coder", "priority": 4},
                ],
                "estimated_hours": 16,
            },
            rationale="Breaking down the product catalog into reusable components for better maintainability.",
            status=PlanStatus.APPROVED.value,
            approved_by_id=pm_id,
        )
        session.add(plan1)

        # Subtasks for Plan 1
        subtask1 = Subtask(
            id=str(uuid4()),
            task_id=task2_id,
            plan_id=plan1_id,
            title="Create ProductCard component",
            description="Build a reusable ProductCard component with image, title, price, and add-to-cart button.",
            priority=1,
            status=SubtaskStatus.FINALIZED.value,
            assignee_id=tm4.id,  # Charlie (frontend dev)
            assigned_agent_id=agent_ids[2],
        )
        session.add(subtask1)

        subtask2 = Subtask(
            id=str(uuid4()),
            task_id=task2_id,
            plan_id=plan1_id,
            title="Implement filtering logic",
            description="Add category, price range, and search filters with debounced input.",
            priority=2,
            status=SubtaskStatus.IN_REVIEW.value,
            assignee_id=tm4.id,
            assigned_agent_id=agent_ids[0],
        )
        session.add(subtask2)

        subtask3 = Subtask(
            id=str(uuid4()),
            task_id=task2_id,
            plan_id=plan1_id,
            title="Add pagination component",
            description="Implement cursor-based pagination with loading states.",
            priority=3,
            status=SubtaskStatus.PENDING.value,
            assignee_id=tm4.id,
        )
        session.add(subtask3)

        # Plan for Task 3 (pending approval)
        plan2_id = str(uuid4())
        plan2 = Plan(
            id=plan2_id,
            task_id=task3_id,
            project_id=project1_id,
            plan_data={
                "subtasks": [
                    {"title": "Review input validation", "agent_type": "reviewer", "priority": 1},
                    {"title": "Check for SQL injection", "agent_type": "reviewer", "priority": 1},
                    {"title": "Audit authentication flow", "agent_type": "reviewer", "priority": 2},
                    {
                        "title": "Review encryption handling",
                        "agent_type": "reviewer",
                        "priority": 2,
                    },
                ],
                "estimated_hours": 8,
            },
            rationale="Comprehensive security review following OWASP guidelines.",
            status=PlanStatus.PENDING_PM_APPROVAL.value,
        )
        session.add(plan2)

        print(f"  Created 2 plans with subtasks")

        # ============== COMMIT ==============
        await session.commit()

        print("\n" + "=" * 50)
        print("Database seeded successfully!")
        print("=" * 50)
        print("\nTest Credentials:")
        print("-" * 30)
        print("Admin:     admin / admin123")
        print("PM:        demo_pm / demo123")
        print("Developer: dev_bob / demo123")
        print("Developer: dev_charlie / demo123")
        print("-" * 30)
        print(f"\nCreated:")
        print(f"  - 4 Users (1 admin, 1 PM, 2 developers)")
        print(f"  - 1 Team")
        print(f"  - 2 Projects")
        print(f"  - 5 Team Memberships (with PM/ADMIN/DEVELOPER roles)")
        print(f"  - {len(default_agents)} Agents")
        print(f"  - 4 Tasks")
        print(f"  - 2 Plans with subtasks")


if __name__ == "__main__":
    asyncio.run(seed_database())
