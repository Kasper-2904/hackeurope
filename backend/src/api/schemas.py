"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, HttpUrl

from src.core.state import AgentStatus, TaskStatus


# ============== User Schemas ==============


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    full_name: str | None = None


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""

    id: str
    email: str
    username: str
    full_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Schema for authentication token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ============== Team Schemas ==============


class TeamCreate(BaseModel):
    """Schema for creating a new team."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class TeamResponse(BaseModel):
    """Schema for team response."""

    id: str
    name: str
    description: str | None
    owner_id: str
    created_at: datetime
    agent_count: int = 0

    model_config = {"from_attributes": True}


class TeamDetail(TeamResponse):
    """Detailed team response with members."""

    agents: list["AgentResponse"] = []


# ============== Agent Schemas ==============


class AgentRegister(BaseModel):
    """Schema for registering a new agent (MCP server)."""

    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., description="Agent role: coder, reviewer, tester, docs, etc.")
    description: str | None = None
    mcp_endpoint: HttpUrl = Field(..., description="URL where agent's MCP server is running")
    team_id: str | None = Field(None, description="Team to add this agent to")
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Schema for agent response."""

    id: str
    name: str
    role: str
    description: str | None
    mcp_endpoint: str
    status: AgentStatus
    owner_id: str
    team_id: str | None
    created_at: datetime
    last_seen: datetime | None

    model_config = {"from_attributes": True}


class AgentDetail(AgentResponse):
    """Detailed agent response with capabilities."""

    capabilities: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class AgentTokenResponse(BaseModel):
    """Response when registering an agent, includes the agent token."""

    agent: AgentResponse
    token: str
    message: str = "Store this token securely. It will not be shown again."


class AgentCapabilitiesUpdate(BaseModel):
    """Schema for updating agent capabilities (from MCP discovery)."""

    tools: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    supports_sampling: bool = False
    supports_logging: bool = False


# ============== Task Schemas ==============


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    task_type: str = Field(
        ...,
        description="Type of task: code_generation, code_review, test_generation, documentation, bug_fix, refactor",
    )
    input_data: dict[str, Any] = Field(default_factory=dict)
    team_id: str | None = None
    assigned_agent_id: str | None = Field(
        None,
        description="Specific agent to assign. If None, orchestrator will choose.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    """Schema for task response."""

    id: str
    title: str
    description: str | None
    task_type: str
    status: TaskStatus
    progress: float
    assigned_agent_id: str | None
    team_id: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class TaskDetail(TaskResponse):
    """Detailed task response with input/output."""

    input_data: dict[str, Any] = {}
    result: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = {}


class TaskProgress(BaseModel):
    """Schema for task progress update."""

    progress: float = Field(..., ge=0.0, le=1.0)
    message: str | None = None


# ============== MCP Communication Schemas ==============


class MCPToolCall(BaseModel):
    """Schema for calling a tool on an agent."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class MCPToolResult(BaseModel):
    """Schema for tool call result."""

    success: bool
    result: Any = None
    error: str | None = None


class MCPResourceRead(BaseModel):
    """Schema for reading a resource from an agent."""

    uri: str


class MCPResourceContent(BaseModel):
    """Schema for resource content."""

    uri: str
    content: str
    mime_type: str | None = None


# ============== WebSocket Schemas ==============


class WSMessage(BaseModel):
    """Base WebSocket message."""

    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class WSAgentStatus(BaseModel):
    """WebSocket message for agent status update."""

    agent_id: str
    status: AgentStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSTaskUpdate(BaseModel):
    """WebSocket message for task update."""

    task_id: str
    status: TaskStatus
    progress: float
    message: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============== Project Schemas ==============


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    goals: list[str] = Field(default_factory=list)
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    timeline: dict[str, Any] = Field(default_factory=dict)
    github_repo: str | None = None
    miro_board_id: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    goals: list[str]
    milestones: list[dict[str, Any]]
    timeline: dict[str, Any]
    github_repo: str | None
    miro_board_id: str | None
    owner_id: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# ============== Plan Schemas ==============


class PlanCreate(BaseModel):
    task_id: str
    project_id: str
    plan_data: dict[str, Any] = Field(default_factory=dict)


class PlanResponse(BaseModel):
    id: str
    task_id: str
    project_id: str
    status: str
    plan_data: dict[str, Any]
    approved_by_id: str | None
    approved_at: datetime | None
    rejection_reason: str | None
    version: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# ============== Dashboard Schemas ==============


class PMDashboardResponse(BaseModel):
    project_id: str
    project: ProjectResponse
    team_members: list = Field(default_factory=list)
    tasks_by_status: dict[str, int] = Field(default_factory=dict)
    recent_plans: list = Field(default_factory=list)
    open_risks: list = Field(default_factory=list)
    critical_alerts: list = Field(default_factory=list)
