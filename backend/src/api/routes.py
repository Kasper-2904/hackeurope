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
    DeveloperDashboardResponse,
    MCPToolCall,
    MCPToolResult,
    PlanCreate,
    PlanGenerate,
    PlanGenerateResponse,
    PlanReject,
    PlanResponse,
    PlanSubmitForApproval,
    PMDashboardResponse,
    ProjectCreate,
    ProjectResponse,
    ReviewerFinalizeRequest,
    ReviewerFinalizeResponse,
    RiskSignalCreate,
    RiskSignalResolve,
    RiskSignalResponse,
    SubtaskCreate,
    SubtaskDetail,
    SubtaskFinalize,
    SubtaskResponse,
    SubtaskUpdate,
    TaskCreate,
    TaskDetail,
    TaskResponse,
    TeamCreate,
    TeamMemberCreate,
    TeamMemberResponse,
    TeamMemberUpdate,
    TeamResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from src.config import get_settings
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import AgentStatus, PlanStatus, TaskStatus
from src.mcp_client.manager import get_mcp_manager
from src.services.paid_service import get_paid_service
from src.storage.database import get_db
from src.storage.models import (
    Agent,
    AuditLog,
    Plan,
    Project,
    RiskSignal,
    Subtask,
    Task,
    Team,
    TeamMember,
    User,
)

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

    if connection.status != AgentStatus.ONLINE:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to agent's MCP server",
        )

    # Update agent status and capabilities in database
    agent.status = AgentStatus.ONLINE
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

    # Log usage to Paid.ai
    paid_service = get_paid_service()
    customer_id = agent.team_id if agent.team_id else current_user.id
    paid_service.record_usage(
        product_id=agent_id,
        customer_id=customer_id,
        event_name="tool_call",
        data={"tool_name": tool_name, "success": tool_result.get("success", False)},
    )

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
        status=TaskStatus.PENDING,
        extra_data=task_data.metadata,
    )

    if task_data.assigned_agent_id:
        task.status = TaskStatus.ASSIGNED
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


@plans_router.post("/generate", response_model=PlanGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_plan(
    plan_data: PlanGenerate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Generate a plan for a task using the OA (Claude + shared context)."""
    from src.core.orchestrator import get_orchestrator

    # Look up the task — scoped to current user
    result = await db.execute(
        select(Task).where(Task.id == plan_data.task_id, Task.created_by_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Verify project exists and belongs to current user
    proj_result = await db.execute(
        select(Project).where(
            Project.id == plan_data.project_id, Project.owner_id == current_user.id
        )
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    orchestrator = get_orchestrator()
    result_data = await orchestrator.generate_plan(
        task_id=task.id,
        task_title=task.title,
        task_description=task.description or "",
        project_id=plan_data.project_id,
        db=db,
    )

    await db.commit()
    return result_data


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

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="plan_approved",
        resource_type="plan",
        resource_id=plan_id,
        details={"version": plan.version},
        previous_state={"status": PlanStatus.PENDING_PM_APPROVAL.value},
        new_state={"status": PlanStatus.APPROVED.value},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(plan)
    return plan


@plans_router.post("/{plan_id}/reject", response_model=PlanResponse)
async def reject_plan(
    plan_id: str,
    rejection: PlanReject,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Plan:
    """Reject a plan (PM rejection with reason)."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    if plan.status != PlanStatus.PENDING_PM_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan must be in pending_pm_approval status to be rejected",
        )

    plan.status = PlanStatus.REJECTED.value
    plan.rejection_reason = rejection.rejection_reason

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="plan_rejected",
        resource_type="plan",
        resource_id=plan_id,
        details={"version": plan.version, "reason": rejection.rejection_reason},
        previous_state={"status": PlanStatus.PENDING_PM_APPROVAL.value},
        new_state={"status": PlanStatus.REJECTED.value},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(plan)
    return plan


@plans_router.post("/{plan_id}/submit", response_model=PlanResponse)
async def submit_plan_for_approval(
    plan_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Plan:
    """Submit a draft plan for PM approval."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    if plan.status != PlanStatus.DRAFT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan must be in draft status to be submitted for approval",
        )

    plan.status = PlanStatus.PENDING_PM_APPROVAL.value

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="plan_submitted",
        resource_type="plan",
        resource_id=plan_id,
        details={"version": plan.version},
        previous_state={"status": PlanStatus.DRAFT.value},
        new_state={"status": PlanStatus.PENDING_PM_APPROVAL.value},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(plan)
    return plan


@plans_router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Plan:
    """Get a plan by ID."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    return plan


# ============== Subtask Routes ==============

subtasks_router = APIRouter(prefix="/subtasks", tags=["Subtasks"])


@subtasks_router.post("", response_model=SubtaskResponse, status_code=status.HTTP_201_CREATED)
async def create_subtask(
    subtask_data: SubtaskCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Subtask:
    """Create a new subtask."""
    from src.core.state import SubtaskStatus

    subtask = Subtask(
        id=str(uuid4()),
        task_id=subtask_data.task_id,
        plan_id=subtask_data.plan_id,
        title=subtask_data.title,
        description=subtask_data.description,
        priority=subtask_data.priority,
        assignee_id=subtask_data.assignee_id,
        assigned_agent_id=subtask_data.assigned_agent_id,
        status=SubtaskStatus.PENDING.value,
    )
    db.add(subtask)
    await db.commit()
    await db.refresh(subtask)
    return subtask


@subtasks_router.get("/{subtask_id}", response_model=SubtaskDetail)
async def get_subtask(
    subtask_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Subtask:
    """Get subtask details."""
    result = await db.execute(select(Subtask).where(Subtask.id == subtask_id))
    subtask = result.scalar_one_or_none()

    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found")

    return subtask


@subtasks_router.patch("/{subtask_id}", response_model=SubtaskResponse)
async def update_subtask(
    subtask_id: str,
    update_data: SubtaskUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Subtask:
    """Update a subtask."""
    result = await db.execute(select(Subtask).where(Subtask.id == subtask_id))
    subtask = result.scalar_one_or_none()

    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            if field == "status":
                setattr(subtask, field, value.value)
            else:
                setattr(subtask, field, value)

    await db.commit()
    await db.refresh(subtask)
    return subtask


@subtasks_router.post("/{subtask_id}/finalize", response_model=SubtaskResponse)
async def finalize_subtask(
    subtask_id: str,
    finalize_data: SubtaskFinalize,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Subtask:
    """Finalize a subtask with the final content."""
    from src.core.state import SubtaskStatus

    result = await db.execute(select(Subtask).where(Subtask.id == subtask_id))
    subtask = result.scalar_one_or_none()

    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found")

    subtask.final_content = finalize_data.final_content
    subtask.finalized_at = datetime.utcnow()
    subtask.finalized_by_id = current_user.id
    subtask.status = SubtaskStatus.FINALIZED.value

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="subtask_finalized",
        resource_type="subtask",
        resource_id=subtask_id,
        details={"final_content": finalize_data.final_content},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(subtask)
    return subtask


# ============== Team Member Routes ==============

team_members_router = APIRouter(prefix="/team-members", tags=["Team Members"])


@team_members_router.post(
    "", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED
)
async def add_team_member(
    member_data: TeamMemberCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamMember:
    """Add a team member to a project."""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(
            Project.id == member_data.project_id, Project.owner_id == current_user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    member = TeamMember(
        id=str(uuid4()),
        user_id=member_data.user_id,
        project_id=member_data.project_id,
        role=member_data.role.value,
        skills=member_data.skills,
        capacity=member_data.capacity,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@team_members_router.get("/project/{project_id}", response_model=list[TeamMemberResponse])
async def list_team_members(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TeamMember]:
    """List team members for a project."""
    result = await db.execute(select(TeamMember).where(TeamMember.project_id == project_id))
    return list(result.scalars().all())


@team_members_router.patch("/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: str,
    update_data: TeamMemberUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamMember:
    """Update a team member."""
    result = await db.execute(select(TeamMember).where(TeamMember.id == member_id))
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            if field == "role":
                setattr(member, field, value.value)
            else:
                setattr(member, field, value)

    await db.commit()
    await db.refresh(member)
    return member


# ============== Risk Signal Routes ==============

risks_router = APIRouter(prefix="/risks", tags=["Risk Signals"])


@risks_router.post("", response_model=RiskSignalResponse, status_code=status.HTTP_201_CREATED)
async def create_risk_signal(
    risk_data: RiskSignalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RiskSignal:
    """Create a risk signal (typically by Reviewer Agent)."""
    risk = RiskSignal(
        id=str(uuid4()),
        project_id=risk_data.project_id,
        task_id=risk_data.task_id,
        subtask_id=risk_data.subtask_id,
        source=risk_data.source.value,
        severity=risk_data.severity.value,
        title=risk_data.title,
        description=risk_data.description,
        rationale=risk_data.rationale,
        recommended_action=risk_data.recommended_action,
    )
    db.add(risk)
    await db.commit()
    await db.refresh(risk)
    return risk


@risks_router.get("/project/{project_id}", response_model=list[RiskSignalResponse])
async def list_project_risks(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_resolved: bool = False,
) -> list[RiskSignal]:
    """List risk signals for a project."""
    query = select(RiskSignal).where(RiskSignal.project_id == project_id)
    if not include_resolved:
        query = query.where(RiskSignal.is_resolved == False)
    query = query.order_by(RiskSignal.created_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


@risks_router.post("/{risk_id}/resolve", response_model=RiskSignalResponse)
async def resolve_risk_signal(
    risk_id: str,
    resolve_data: RiskSignalResolve,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RiskSignal:
    """Resolve a risk signal."""
    result = await db.execute(select(RiskSignal).where(RiskSignal.id == risk_id))
    risk = result.scalar_one_or_none()

    if not risk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk signal not found")

    risk.is_resolved = True
    risk.resolved_at = datetime.utcnow()
    risk.resolved_by_id = current_user.id

    # Create audit log
    audit = AuditLog(
        id=str(uuid4()),
        user_id=current_user.id,
        action="risk_resolved",
        resource_type="risk_signal",
        resource_id=risk_id,
        details={"resolution_note": resolve_data.resolution_note},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(risk)
    return risk


# ============== Dashboard Routes ==============

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboards"])


@dashboard_router.get("/pm/{project_id}", response_model=PMDashboardResponse)
async def pm_dashboard(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get PM dashboard data."""
    from src.core.state import RiskSeverity

    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Get team members
    members_result = await db.execute(select(TeamMember).where(TeamMember.project_id == project_id))
    team_members = list(members_result.scalars().all())

    # Get tasks by status (tasks linked to project via plans)
    plans_result = await db.execute(
        select(Plan).where(Plan.project_id == project_id).order_by(Plan.created_at.desc()).limit(10)
    )
    recent_plans = list(plans_result.scalars().all())

    # Get open risks
    risks_result = await db.execute(
        select(RiskSignal)
        .where(
            RiskSignal.project_id == project_id,
            RiskSignal.is_resolved == False,
        )
        .order_by(RiskSignal.created_at.desc())
    )
    open_risks = list(risks_result.scalars().all())

    # Critical alerts are high/critical severity unresolved risks
    critical_alerts = [
        r
        for r in open_risks
        if r.severity in [RiskSeverity.HIGH.value, RiskSeverity.CRITICAL.value]
    ]

    return {
        "project_id": project_id,
        "project": project,
        "team_members": team_members,
        "tasks_by_status": {},  # TODO: Aggregate from tasks linked to project
        "recent_plans": recent_plans,
        "open_risks": open_risks,
        "critical_alerts": critical_alerts,
    }


@dashboard_router.get("/developer/{user_id}", response_model=DeveloperDashboardResponse)
async def developer_dashboard(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get developer dashboard data."""
    from src.core.state import SubtaskStatus

    # Ensure user can only access their own dashboard (or is admin)
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's dashboard",
        )

    # Get tasks assigned to this user (as creator for now)
    tasks_result = await db.execute(
        select(Task).where(Task.created_by_id == user_id).order_by(Task.created_at.desc())
    )
    assigned_tasks = list(tasks_result.scalars().all())

    # Get team memberships for this user
    memberships_result = await db.execute(select(TeamMember).where(TeamMember.user_id == user_id))
    memberships = list(memberships_result.scalars().all())
    member_ids = [m.id for m in memberships]

    # Get subtasks assigned to user via team memberships
    assigned_subtasks = []
    pending_reviews = []
    if member_ids:
        subtasks_result = await db.execute(
            select(Subtask).where(Subtask.assignee_id.in_(member_ids))
        )
        all_subtasks = list(subtasks_result.scalars().all())
        assigned_subtasks = [s for s in all_subtasks if s.status != SubtaskStatus.IN_REVIEW.value]
        pending_reviews = [s for s in all_subtasks if s.status == SubtaskStatus.IN_REVIEW.value]

    # Get recent risks for projects user is part of
    project_ids = [m.project_id for m in memberships]
    recent_risks = []
    if project_ids:
        risks_result = await db.execute(
            select(RiskSignal)
            .where(
                RiskSignal.project_id.in_(project_ids),
                RiskSignal.is_resolved == False,
            )
            .order_by(RiskSignal.created_at.desc())
            .limit(10)
        )
        recent_risks = list(risks_result.scalars().all())

    # Calculate workload
    workload = sum(m.current_load for m in memberships) / max(len(memberships), 1)

    return {
        "user_id": user_id,
        "assigned_tasks": assigned_tasks,
        "assigned_subtasks": assigned_subtasks,
        "pending_reviews": pending_reviews,
        "recent_risks": recent_risks,
        "workload": workload,
    }


# ============== Reviewer Routes ==============

reviewer_router = APIRouter(prefix="/reviewer", tags=["Reviewer Agent"])


@reviewer_router.get("/risks/{project_id}", response_model=list[RiskSignalResponse])
async def get_reviewer_risks(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RiskSignal]:
    """Get all risk signals for a project from the reviewer agent perspective."""
    result = await db.execute(
        select(RiskSignal)
        .where(RiskSignal.project_id == project_id)
        .order_by(
            RiskSignal.severity.desc(),
            RiskSignal.created_at.desc(),
        )
    )
    return list(result.scalars().all())


@reviewer_router.post(
    "/finalize/{task_id}",
    response_model=ReviewerFinalizeResponse,
)
async def finalize_task_review(
    task_id: str,
    body: ReviewerFinalizeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Run the Reviewer Agent on a completed task.

    Analyzes consistency, conflicts, quality, and returns merge-readiness.
    Creates RiskSignal rows for any findings.
    """
    from src.services.reviewer_service import get_reviewer_service

    # Verify task belongs to current user
    task_result = await db.execute(
        select(Task).where(Task.id == task_id, Task.created_by_id == current_user.id)
    )
    if not task_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Verify project belongs to current user
    proj_result = await db.execute(
        select(Project).where(
            Project.id == body.project_id, Project.owner_id == current_user.id
        )
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    reviewer = get_reviewer_service()
    try:
        result = await reviewer.finalize_task(task_id, body.project_id, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    await db.commit()
    return result
