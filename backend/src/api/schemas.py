"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, HttpUrl

from src.core.state import (
    AgentStatus,
    PlanStatus,
    RiskSeverity,
    RiskSource,
    SubtaskStatus,
    TaskStatus,
    UserRole,
)


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


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    goals: list[str]
    milestones: list[dict[str, Any]]
    timeline: dict[str, Any]
    github_repo: str | None
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


# ============== TeamMember Schemas ==============


class TeamMemberCreate(BaseModel):
    """Schema for adding a team member to a project."""

    user_id: str
    project_id: str
    role: UserRole = UserRole.DEVELOPER
    skills: list[str] = Field(default_factory=list)
    capacity: float = Field(1.0, ge=0.0, le=1.0)


class TeamMemberResponse(BaseModel):
    """Schema for team member response."""

    id: str
    user_id: str
    project_id: str
    role: str
    skills: list[str]
    capacity: float
    current_load: float
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class TeamMemberUpdate(BaseModel):
    """Schema for updating team member."""

    role: UserRole | None = None
    skills: list[str] | None = None
    capacity: float | None = Field(None, ge=0.0, le=1.0)


# ============== Subtask Schemas ==============


class SubtaskCreate(BaseModel):
    """Schema for creating a subtask."""

    task_id: str
    plan_id: str | None = None
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    priority: int = 0
    assignee_id: str | None = None
    assigned_agent_id: str | None = None


class SubtaskResponse(BaseModel):
    """Schema for subtask response."""

    id: str
    task_id: str
    plan_id: str | None
    title: str
    description: str | None
    priority: int
    status: str
    assignee_id: str | None
    assigned_agent_id: str | None
    draft_version: int
    risk_flags: list[str]
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class SubtaskDetail(SubtaskResponse):
    """Detailed subtask response including draft and final content."""

    draft_content: dict[str, Any] | None = None
    draft_generated_at: datetime | None = None
    draft_agent_id: str | None = None
    final_content: dict[str, Any] | None = None
    finalized_at: datetime | None = None
    finalized_by_id: str | None = None


class SubtaskUpdate(BaseModel):
    """Schema for updating a subtask."""

    title: str | None = None
    description: str | None = None
    priority: int | None = None
    status: SubtaskStatus | None = None
    assignee_id: str | None = None
    assigned_agent_id: str | None = None


class SubtaskFinalize(BaseModel):
    """Schema for finalizing a subtask."""

    final_content: dict[str, Any]


# ============== RiskSignal Schemas ==============


class RiskSignalCreate(BaseModel):
    """Schema for creating a risk signal."""

    project_id: str
    task_id: str | None = None
    subtask_id: str | None = None
    source: RiskSource
    severity: RiskSeverity
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    rationale: str | None = None
    recommended_action: str | None = None


class RiskSignalResponse(BaseModel):
    """Schema for risk signal response."""

    id: str
    project_id: str
    task_id: str | None
    subtask_id: str | None
    source: str
    severity: str
    title: str
    description: str | None
    rationale: str | None
    recommended_action: str | None
    is_resolved: bool
    resolved_at: datetime | None
    resolved_by_id: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class RiskSignalResolve(BaseModel):
    """Schema for resolving a risk signal."""

    resolution_note: str | None = None


# ============== AuditLog Schemas ==============


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""

    id: str
    user_id: str | None
    agent_id: str | None
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any]
    previous_state: dict[str, Any] | None
    new_state: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============== Dashboard Schemas ==============


class DeveloperDashboardResponse(BaseModel):
    """Schema for developer dashboard response."""

    user_id: str
    assigned_tasks: list[TaskResponse] = Field(default_factory=list)
    assigned_subtasks: list[SubtaskResponse] = Field(default_factory=list)
    pending_reviews: list[SubtaskResponse] = Field(default_factory=list)
    recent_risks: list[RiskSignalResponse] = Field(default_factory=list)
    workload: float = 0.0


class PMDashboardResponse(BaseModel):
    """Schema for PM dashboard response."""

    project_id: str
    project: ProjectResponse
    team_members: list[TeamMemberResponse] = Field(default_factory=list)
    tasks_by_status: dict[str, int] = Field(default_factory=dict)
    recent_plans: list[PlanResponse] = Field(default_factory=list)
    open_risks: list[RiskSignalResponse] = Field(default_factory=list)
    critical_alerts: list[RiskSignalResponse] = Field(default_factory=list)


# ============== Plan Submission Schema ==============


class PlanSubmitForApproval(BaseModel):
    """Schema for submitting a plan for PM approval."""

    pass  # No additional fields needed, just changes status


class PlanReject(BaseModel):
    """Schema for rejecting a plan."""

    rejection_reason: str = Field(..., min_length=1)


class PlanGenerate(BaseModel):
    """Schema for OA-driven plan generation from task + project context."""

    task_id: str
    project_id: str


class PlanGenerateResponse(BaseModel):
    """Response from OA plan generation."""

    task_id: str
    plan_id: str | None
    status: str
    plan_data: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None
    error: str | None = None


class ReviewerFinalizeRequest(BaseModel):
    """Request body for reviewer finalize endpoint."""

    project_id: str


class ReviewerFinalizeResponse(BaseModel):
    """Response from reviewer analysis."""

    task_id: str
    merge_ready: bool
    findings: list[dict[str, Any]] = Field(default_factory=list)
    risks_created: int = 0
    summary: str = ""
    error: str | None = None
