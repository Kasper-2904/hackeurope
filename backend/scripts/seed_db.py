"""Seed script to populate agents and demo data."""

import asyncio
from uuid import uuid4
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import get_settings
from sqlalchemy import select
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
    RiskSignal,
    AuditLog,
    AgentSubscription,
    UsageRecord,
    GitHubContext,
    SellerProfile,
    ProjectAllowedAgent,
)
from src.core.state import (
    AgentStatus,
    PricingType,
    UserRole,
    TaskStatus,
    PlanStatus,
    SubtaskStatus,
    RiskSeverity,
    RiskSource,
    SubscriptionStatus,
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
        # Idempotency check
        existing = await session.execute(
            select(User).where(User.email == "admin@unifai.com")
        )
        if existing.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        print("=" * 50)
        print("Seeding Database...")
        print("=" * 50)

        # ============== USERS ==============
        print("\n[1/14] Creating Users...")

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
        print("\n[2/14] Creating Teams...")

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
        print("\n[3/14] Creating Projects...")

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
        print("\n[4/14] Creating Team Members with Roles...")

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
        print("\n[5/14] Creating Agents...")

        # Platform agents - powered by Anthropic Claude
        platform_agents = [
            {
                "name": "Claude Code Assistant",
                "role": "coder",
                "description": "Powered by Claude. Expert in writing, reviewing, and explaining code across multiple languages.",
                "inference_endpoint": "",
                "access_token": settings.anthropic_api_key or "",
                "inference_provider": "anthropic",
                "inference_model": "claude-sonnet-4-20250514",
                "system_prompt": "You are Claude, an expert software developer. Help users write clean, efficient code.",
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
                "owner_id": admin_id,
            },
            {
                "name": "Qwen3 Research Assistant",
                "role": "researcher",
                "description": "Powered by Qwen3-235B on Crusoe Cloud. Expert in research, analysis, summarization, and answering complex questions.",
                "inference_endpoint": settings.crusoe_api_base
                or "https://hackeurope.crusoecloud.com/v1",
                "access_token": settings.crusoe_api_key or "",
                "inference_provider": "crusoe",
                "inference_model": "NVFP4/Qwen3-235B-A22B-Instruct-2507-FP4",
                "system_prompt": "You are Qwen3, an expert research assistant. Help users analyze information, summarize documents, answer complex questions, and provide well-reasoned insights. Be thorough yet concise.",
                "skills": [
                    "research",
                ],
                "category": "Research",
                "pricing_type": PricingType.FREE.value,
                "price": 0.0,
                "owner_id": admin_id,
            },
            {
                "name": "Claude Security Reviewer",
                "role": "reviewer",
                "description": "Powered by Claude. Performs security analysis and checks for OWASP vulnerabilities.",
                "inference_endpoint": "",
                "access_token": settings.anthropic_api_key or "",
                "inference_provider": "anthropic",
                "inference_model": "claude-sonnet-4-20250514",
                "system_prompt": "You are a security expert. Review code for vulnerabilities and suggest fixes following OWASP guidelines.",
                "skills": ["review_code", "check_security", "suggest_improvements"],
                "category": "Security",
                "pricing_type": PricingType.FREE.value,
                "price": 0.0,
                "owner_id": admin_id,
            },
            {
                "name": "Claude Frontend Expert",
                "role": "designer",
                "description": "Powered by Claude. Creates React components and modern UI with TailwindCSS.",
                "inference_endpoint": "",
                "access_token": settings.anthropic_api_key or "",
                "inference_provider": "anthropic",
                "inference_model": "claude-sonnet-4-20250514",
                "system_prompt": "You are a frontend expert. Create modern, accessible React components with TailwindCSS.",
                "skills": ["generate_code", "design_component", "suggest_improvements"],
                "category": "Frontend",
                "pricing_type": PricingType.FREE.value,
                "price": 0.0,
                "owner_id": admin_id,
            },
        ]

        # Seller-hosted agent example - simulates a third-party seller
        seller_agents = [
            {
                "name": "DevOps Pro Agent",
                "role": "coder",
                "description": "Third-party seller agent. Expert in Docker, Kubernetes, CI/CD pipelines, and infrastructure as code.",
                "inference_endpoint": "https://seller-devops-agent.example.com/v1",
                "access_token": "seller_token_devops_abc123xyz",
                "inference_provider": "openai-compatible",
                "inference_model": "gpt-4o",
                "system_prompt": "You are a DevOps expert. Help with containerization, deployment, and infrastructure automation.",
                "skills": ["generate_code", "debug_code", "suggest_improvements"],
                "category": "DevOps",
                "pricing_type": PricingType.USAGE_BASED.value,
                "price": 0.05,
                "owner_id": dev1_id,  # Seller is dev1
            },
        ]

        default_agents = platform_agents + seller_agents

        agent_ids = []
        for agent_data in default_agents:
            agent_id = str(uuid4())
            agent_ids.append(agent_id)

            # Create the agent
            agent = Agent(
                id=agent_id,
                name=agent_data["name"],
                role=agent_data["role"],
                description=agent_data["description"],
                inference_endpoint=agent_data["inference_endpoint"],
                inference_api_key_encrypted=agent_data["access_token"],
                inference_provider=agent_data["inference_provider"],
                inference_model=agent_data["inference_model"],
                system_prompt=agent_data["system_prompt"],
                skills=agent_data["skills"],
                owner_id=agent_data["owner_id"],
                team_id=team_id if agent_data["owner_id"] == admin_id else None,
                status=AgentStatus.ONLINE,
            )
            session.add(agent)

            # Marketplace listing
            market_agent = MarketplaceAgent(
                id=str(uuid4()),
                agent_id=agent_id,
                seller_id=agent_data["owner_id"],
                name=agent_data["name"],
                description=agent_data["description"],
                category=agent_data["category"],
                pricing_type=agent_data["pricing_type"],
                price_per_use=agent_data["price"],
                is_verified=agent_data["owner_id"] == admin_id,  # Platform agents are verified
                is_active=True,
            )
            session.add(market_agent)

        print(
            f"  Created {len(platform_agents)} platform agents + {len(seller_agents)} seller agent"
        )

        # ============== TASKS ==============
        print("\n[6/14] Creating Tasks...")

        task1_id = str(uuid4())
        task1 = Task(
            id=task1_id,
            title="Implement User Authentication API",
            description="Create JWT-based authentication endpoints including login, register, refresh token, and logout.",
            task_type="code_generation",
            status=TaskStatus.COMPLETED,
            team_id=team_id,
            created_by_id=pm_id,
            assigned_agent_id=agent_ids[0],  # Claude Code Assistant
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
            assigned_agent_id=agent_ids[0],  # Claude Code Assistant
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
            assigned_agent_id=agent_ids[0],  # Claude Code Assistant
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
            assigned_agent_id=agent_ids[0],  # Claude Code Assistant
            progress=0.0,
        )
        session.add(task4)

        print(f"  Created 4 tasks")

        # ============== PLANS ==============
        print("\n[7/14] Creating Plans and Subtasks...")

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
            assigned_agent_id=agent_ids[0],  # Claude Code Assistant
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
            assigned_agent_id=agent_ids[0],  # Claude Code Assistant
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

        # ============== SELLER PROFILES ==============
        print("\n[8/14] Creating Seller Profiles...")

        seller_profile = SellerProfile(
            id=str(uuid4()),
            user_id=dev1_id,
            stripe_account_id="acct_seller_dev1_demo",
            payout_enabled=True,
            total_earnings=42.50,
        )
        session.add(seller_profile)
        print(f"  Created 1 seller profile (dev_bob)")

        # ============== AGENT SUBSCRIPTIONS ==============
        print("\n[9/14] Creating Agent Subscriptions...")

        # We need marketplace_agent IDs — look up by name for deterministic results
        ma_result = await session.execute(select(MarketplaceAgent))
        marketplace_agents = list(ma_result.scalars().all())
        ma_by_name = {ma.name: ma.id for ma in marketplace_agents}

        sub1 = AgentSubscription(
            id=str(uuid4()),
            team_id=team_id,
            marketplace_agent_id=ma_by_name["Claude Code Assistant"],
            status=SubscriptionStatus.ACTIVE.value,
        )
        session.add(sub1)

        sub2 = AgentSubscription(
            id=str(uuid4()),
            team_id=team_id,
            marketplace_agent_id=ma_by_name["Claude Security Reviewer"],
            status=SubscriptionStatus.ACTIVE.value,
        )
        session.add(sub2)
        print(f"  Created 2 agent subscriptions")

        # ============== PROJECT ALLOWED AGENTS ==============
        print("\n[10/14] Creating Project Allowed Agents...")

        for i, aid in enumerate(agent_ids[:3]):
            paa = ProjectAllowedAgent(
                id=str(uuid4()),
                project_id=project1_id,
                agent_id=aid,
                added_by_id=pm_id,
            )
            session.add(paa)
        print(f"  Created 3 project-allowed-agent entries")

        # ============== RISK SIGNALS ==============
        print("\n[11/14] Creating Risk Signals...")

        risk1 = RiskSignal(
            id=str(uuid4()),
            project_id=project1_id,
            task_id=task2_id,
            source=RiskSource.MERGE_CONFLICT.value,
            severity=RiskSeverity.CRITICAL.value,
            title="Potential merge conflict in auth module",
            description="Two subtasks modify the same authentication middleware file.",
            rationale="Files overlapping: src/middleware/auth.ts modified by subtask 1 and subtask 2.",
            recommended_action="Coordinate merge order — finalize subtask 1 first.",
        )
        session.add(risk1)

        risk2 = RiskSignal(
            id=str(uuid4()),
            project_id=project1_id,
            task_id=task3_id,
            source=RiskSource.SECURITY.value,
            severity=RiskSeverity.MEDIUM.value,
            title="SQL injection risk in search endpoint",
            description="User input concatenated directly into query string.",
            recommended_action="Use parameterized queries.",
        )
        session.add(risk2)

        risk3 = RiskSignal(
            id=str(uuid4()),
            project_id=project1_id,
            task_id=task1_id,
            source=RiskSource.CI_FAILURE.value,
            severity=RiskSeverity.LOW.value,
            title="Flaky test in auth suite",
            description="test_token_refresh fails intermittently on CI.",
            is_resolved=True,
            resolved_by_id=dev1_id,
        )
        session.add(risk3)
        print(f"  Created 3 risk signals (1 resolved, 2 open)")

        # ============== AUDIT LOGS ==============
        print("\n[12/14] Creating Audit Logs...")

        audit_entries = [
            {
                "user_id": pm_id,
                "action": "plan_approved",
                "resource_type": "plan",
                "resource_id": plan1_id,
                "details": {"plan_title": "Product Catalog Plan"},
            },
            {
                "user_id": dev2_id,
                "action": "subtask_finalized",
                "resource_type": "subtask",
                "resource_id": subtask1.id,
                "details": {"subtask_title": "Create ProductCard component"},
            },
            {
                "user_id": dev1_id,
                "action": "risk_resolved",
                "resource_type": "risk_signal",
                "resource_id": risk3.id,
                "details": {"resolution_note": "Fixed flaky test with retry logic"},
            },
            {
                "user_id": pm_id,
                "action": "task_created",
                "resource_type": "task",
                "resource_id": task1_id,
                "details": {"task_title": "Implement User Authentication API"},
            },
        ]
        for entry in audit_entries:
            audit = AuditLog(id=str(uuid4()), **entry)
            session.add(audit)
        print(f"  Created {len(audit_entries)} audit log entries")

        # ============== USAGE RECORDS ==============
        print("\n[13/14] Creating Usage Records...")

        usage_entries = [
            {"usage_type": "plan_generation", "quantity": 1, "cost": 0.05, "user_id": pm_id},
            {"usage_type": "tool_call", "quantity": 3, "cost": 0.15, "user_id": dev1_id},
            {"usage_type": "tool_call", "quantity": 2, "cost": 0.10, "user_id": dev2_id},
            {"usage_type": "reviewer_finalize", "quantity": 1, "cost": 0.08, "user_id": pm_id},
            {"usage_type": "tool_call", "quantity": 1, "cost": 0.05, "user_id": dev1_id},
        ]
        for entry in usage_entries:
            usage = UsageRecord(
                id=str(uuid4()),
                team_id=team_id,
                marketplace_agent_id=ma_ids[0],
                **entry,
            )
            session.add(usage)
        print(f"  Created {len(usage_entries)} usage records")

        # ============== GITHUB CONTEXT ==============
        print("\n[14/14] Creating GitHub Context...")

        github_ctx = GitHubContext(
            id=str(uuid4()),
            project_id=project1_id,
            pull_requests=[
                {
                    "number": 42,
                    "title": "feat: add product catalog component",
                    "state": "open",
                    "author": "dev_charlie",
                    "additions": 340,
                    "deletions": 12,
                },
                {
                    "number": 41,
                    "title": "fix: auth token refresh race condition",
                    "state": "merged",
                    "author": "dev_bob",
                    "additions": 28,
                    "deletions": 15,
                },
            ],
            recent_commits=[
                {"sha": "abc1234", "message": "feat: ProductCard component", "author": "dev_charlie"},
                {"sha": "def5678", "message": "fix: token refresh logic", "author": "dev_bob"},
                {"sha": "ghi9012", "message": "chore: update CI config", "author": "dev_bob"},
            ],
            ci_status=[
                {"workflow": "tests", "status": "success", "branch": "main"},
                {"workflow": "lint", "status": "success", "branch": "main"},
                {"workflow": "tests", "status": "failure", "branch": "feat/catalog"},
            ],
        )
        session.add(github_ctx)
        print(f"  Created GitHub context for project 1")

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
        print(f"  - {len(platform_agents)} Platform Agents + {len(seller_agents)} Seller Agent")
        print(f"  - 4 Tasks")
        print(f"  - 2 Plans with subtasks")
        print(f"  - 1 Seller Profile")
        print(f"  - 2 Agent Subscriptions")
        print(f"  - 3 Project Allowed Agents")
        print(f"  - 3 Risk Signals")
        print(f"  - {len(audit_entries)} Audit Log Entries")
        print(f"  - {len(usage_entries)} Usage Records")
        print(f"  - 1 GitHub Context")


if __name__ == "__main__":
    asyncio.run(seed_database())
