"""API routes for the agent orchestrator platform."""

from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import (
    create_access_token,
    create_agent_token,
    get_current_user,
    get_password_hash,
    verify_agent_token,
    verify_password,
)
from src.api.schemas import (
    AgentCapabilitiesUpdate,
    AgentDetail,
    AgentRegister,
    AgentResponse,
    AgentTokenResponse,
    MCPToolCall,
    MCPToolResult,
    PlanCreate,
    PlanResponse,
    PMDashboardResponse,
    ProjectCreate,
    ProjectResponse,
    TaskCreate,
    TaskDetail,
    TaskResponse,
    TeamCreate,
    TeamResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from src.config import get_settings
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import AgentStatus as ModelAgentStatus, TaskStatus as ModelTaskStatus
from src.storage.models import AgentStatus, TaskStatus
from src.mcp_client.manager import get_mcp_manager
from src.storage.database import get_db
from src.storage.models import Agent, Plan, PlanStatus, Project, Task, Team, User

# ============== Routers ==============

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
users_router = APIRouter(prefix="/users", tags=["Users"])
teams_router = APIRouter(prefix="/teams", tags=["Teams"])
agents_router = APIRouter(prefix="/agents", tags=["Agents"])
tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])


# ============== Auth Routes ==============


@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Register a new user."""
    # Check if email or username already exists
    result = await db.execute(
        select(User).where((User.email == user_data.email) | (User.username == user_data.username))
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered",
        )

    # Create new user
    user = User(
        id=str(uuid4()),
        email=user_data.email,
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Login and get access token."""
    # Find user by username
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    settings = get_settings()
    access_token = create_access_token(data={"sub": user.id, "type": "user"})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user information."""
    return current_user


# ============== Team Routes ==============


@teams_router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_data: TeamCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Team:
    """Create a new team."""
    team = Team(
        id=str(uuid4()),
        name=team_data.name,
        description=team_data.description,
        owner_id=current_user.id,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)

    return team


@teams_router.get("", response_model=list[TeamResponse])
async def list_teams(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Team]:
    """List teams owned by the current user."""
    result = await db.execute(select(Team).where(Team.owner_id == current_user.id))
    return list(result.scalars().all())


@teams_router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Team:
    """Get a team by ID."""
    result = await db.execute(
        select(Team).where(Team.id == team_id, Team.owner_id == current_user.id)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    return team


# ============== Agent Routes ==============


@agents_router.post(
    "/register", response_model=AgentTokenResponse, status_code=status.HTTP_201_CREATED
)
async def register_agent(
    agent_data: AgentRegister,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Register a new agent (MCP server) with the platform.

    The agent must be running an MCP server at the specified endpoint.
    Returns an API token that the agent should use for subsequent requests.
    """
    event_bus = get_event_bus()

    # Verify team ownership if team_id provided
    if agent_data.team_id:
        result = await db.execute(
            select(Team).where(Team.id == agent_data.team_id, Team.owner_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found or you don't have access",
            )

    # Create the agent
    agent_id = str(uuid4())
    agent = Agent(
        id=agent_id,
        name=agent_data.name,
        role=agent_data.role,
        description=agent_data.description,
        mcp_endpoint=str(agent_data.mcp_endpoint),
        owner_id=current_user.id,
        team_id=agent_data.team_id,
        status=AgentStatus.PENDING,
        extra_data=agent_data.metadata,
    )

    # Generate agent token
    agent_token = create_agent_token(agent_id)
    # Use SHA256 instead of bcrypt since JWT tokens can be long
    import hashlib

    agent.api_token_hash = hashlib.sha256(agent_token.encode()).hexdigest()

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    # Publish registration event
    await event_bus.publish(
        Event(
            type=EventType.AGENT_REGISTERED,
            data={
                "agent_id": agent_id,
                "name": agent_data.name,
                "role": agent_data.role,
                "mcp_endpoint": str(agent_data.mcp_endpoint),
            },
            source="api",
        )
    )

    return {
        "agent": agent,
        "token": agent_token,
        "message": "Store this token securely. It will not be shown again.",
    }


@agents_router.post("/{agent_id}/connect")
async def connect_to_agent(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Connect to a registered agent's MCP server.

    This will discover the agent's tools and resources.
    """
    # Get agent from database
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Connect via MCP
    mcp_manager = get_mcp_manager()
    connection = await mcp_manager.register_agent(agent_id, agent.mcp_endpoint, connect=True)

    if connection.status != ModelAgentStatus.ONLINE:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to agent's MCP server",
        )

    # Update agent status and capabilities in database
    agent.status = AgentStatus.ONLINE.value
    agent.last_seen = datetime.utcnow()
    agent.capabilities = {
        "tools": [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in connection.capabilities.tools
        ],
        "resources": [
            {
                "uri": str(r.uri),
                "name": r.name,
                "description": r.description,
                "mime_type": r.mime_type,
            }
            for r in connection.capabilities.resources
        ],
    }

    await db.commit()

    return {
        "status": "connected",
        "agent_id": agent_id,
        "capabilities": agent.capabilities,
    }


@agents_router.get("", response_model=list[AgentResponse])
async def list_agents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    team_id: str | None = None,
) -> list[Agent]:
    """List agents owned by the current user, optionally filtered by team."""
    query = select(Agent).where(Agent.owner_id == current_user.id)

    if team_id:
        query = query.where(Agent.team_id == team_id)

    result = await db.execute(query)
    return list(result.scalars().all())


@agents_router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Agent:
    """Get agent details including capabilities."""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    return agent


@agents_router.post("/{agent_id}/tools/{tool_name}", response_model=MCPToolResult)
async def call_agent_tool(
    agent_id: str,
    tool_name: str,
    tool_call: MCPToolCall,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Call a tool on a specific agent.

    The agent must be connected and online.
    """
    # Verify ownership
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Call tool via MCP
    mcp_manager = get_mcp_manager()
    tool_result = await mcp_manager.call_tool(agent_id, tool_name, tool_call.arguments)

    # Update last seen
    agent.last_seen = datetime.utcnow()
    await db.commit()

    return tool_result


# ============== Task Routes ==============


@tasks_router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Task:
    """
    Create a new task.

    If assigned_agent_id is provided, the task will be assigned to that agent.
    Otherwise, the orchestrator will choose an appropriate agent.
    """
    event_bus = get_event_bus()

    task = Task(
        id=str(uuid4()),
        title=task_data.title,
        description=task_data.description,
        task_type=task_data.task_type,
        input_data=task_data.input_data,
        team_id=task_data.team_id,
        assigned_agent_id=task_data.assigned_agent_id,
        created_by_id=current_user.id,
        status=TaskStatus.PENDING.value,
        extra_data=task_data.metadata,
    )

    if task_data.assigned_agent_id:
        task.status = TaskStatus.ASSIGNED.value
        task.assigned_at = datetime.utcnow()

    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Publish task created event
    await event_bus.publish(
        Event(
            type=EventType.TASK_CREATED,
            data={
                "task_id": task.id,
                "task_type": task.task_type,
                "assigned_agent_id": task.assigned_agent_id,
            },
            source="api",
        )
    )

    return task


@tasks_router.get("", response_model=list[TaskResponse])
async def list_tasks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    team_id: str | None = None,
    status: TaskStatus | None = None,
) -> list[Task]:
    """List tasks, optionally filtered by team and status."""
    query = select(Task).where(Task.created_by_id == current_user.id)

    if team_id:
        query = query.where(Task.team_id == team_id)
    if status:
        query = query.where(Task.status == status)

    result = await db.execute(query)
    return list(result.scalars().all())


@tasks_router.get("/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Task:
    """Get task details including input/output."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by_id == current_user.id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return task


# ============== Health & Status ==============

health_router = APIRouter(tags=["Health"])


@health_router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@health_router.get("/agents/status")
async def agents_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Get status of all connected agents."""
    mcp_manager = get_mcp_manager()
    return await mcp_manager.health_check()


# ============== Project Routes ==============

projects_router = APIRouter(prefix="/projects", tags=["Projects"])


@projects_router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Project:
    """Create a new project."""
    project = Project(
        id=str(uuid4()),
        name=project_data.name,
        description=project_data.description,
        goals=project_data.goals,
        milestones=project_data.milestones,
        timeline=project_data.timeline,
        github_repo=project_data.github_repo,
        miro_board_id=project_data.miro_board_id,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@projects_router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Project]:
    """List projects owned by the current user."""
    result = await db.execute(select(Project).where(Project.owner_id == current_user.id))
    return list(result.scalars().all())


# ============== Plan Routes ==============

plans_router = APIRouter(prefix="/plans", tags=["Plans"])


@plans_router.post("/generate", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def generate_plan(
    plan_data: PlanCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Plan:
    """Generate a plan for a task (OA creates draft plan)."""
    plan = Plan(
        id=str(uuid4()),
        task_id=plan_data.task_id,
        project_id=plan_data.project_id,
        plan_data=plan_data.plan_data,
        status=PlanStatus.DRAFT.value,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@plans_router.post("/{plan_id}/approve", response_model=PlanResponse)
async def approve_plan(
    plan_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Plan:
    """Approve a plan (PM approval)."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    if plan.status != PlanStatus.PENDING_PM_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan must be in pending_pm_approval status to be approved",
        )

    plan.status = PlanStatus.APPROVED.value
    plan.approved_by_id = current_user.id
    plan.approved_at = datetime.utcnow()

    await db.commit()
    await db.refresh(plan)
    return plan


# ============== Dashboard Routes ==============

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboards"])


@dashboard_router.get("/pm/{project_id}", response_model=PMDashboardResponse)
async def pm_dashboard(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get PM dashboard data."""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return {
        "project_id": project_id,
        "project": project,
        "team_members": [],
        "tasks_by_status": {},
        "recent_plans": [],
        "open_risks": [],
        "critical_alerts": [],
    }
