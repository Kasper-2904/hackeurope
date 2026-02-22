"""State definitions for agents, tasks, and orchestrator."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class AgentStatus(str, Enum):
    """Status of an agent."""

    PENDING = "pending"  # Registered but not connected
    ONLINE = "online"  # Connected and ready
    BUSY = "busy"  # Currently executing a task
    OFFLINE = "offline"  # Disconnected
    ERROR = "error"  # In error state


class TaskStatus(str, Enum):
    """Status of a task."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStatus(str, Enum):
    """Status of an implementation plan."""

    DRAFT = "draft"
    PENDING_PM_APPROVAL = "pending_pm_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class SubtaskStatus(str, Enum):
    """Status of a subtask."""

    PENDING = "pending"
    DRAFT_GENERATED = "draft_generated"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    FINALIZED = "finalized"
    REJECTED = "rejected"
    FAILED = "failed"
    DONE = "done"


class PricingType(str, Enum):
    """Pricing model for marketplace agents."""

    FREE = "free"
    USAGE_BASED = "usage_based"


class SubscriptionStatus(str, Enum):
    """Status of a Stripe subscription."""

    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class RiskSeverity(str, Enum):
    """Severity level of a risk signal."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskSource(str, Enum):
    """Source of a risk signal."""

    MERGE_CONFLICT = "merge_conflict"
    CI_FAILURE = "ci_failure"
    INTEGRATION = "integration"
    DEPENDENCY = "dependency"
    SECURITY = "security"
    REVIEWER = "reviewer"


class UserRole(str, Enum):
    """User role for access control."""

    ADMIN = "admin"
    PM = "pm"
    DEVELOPER = "developer"


@dataclass
class MCPTool:
    """Represents a tool exposed by an MCP server (agent)."""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None


@dataclass
class MCPResource:
    """Represents a resource exposed by an MCP server (agent)."""

    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None


@dataclass
class AgentCapabilities:
    """Capabilities discovered from an agent's MCP server."""

    tools: list[MCPTool] = field(default_factory=list)
    resources: list[MCPResource] = field(default_factory=list)
    supports_sampling: bool = False
    supports_logging: bool = False


@dataclass
class AgentState:
    """State of a registered agent."""

    agent_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    role: str = ""  # e.g., "coder", "reviewer", "tester"
    description: str | None = None

    # Connection info
    mcp_endpoint: str = ""  # URL where agent's MCP server is running
    status: AgentStatus = AgentStatus.PENDING

    # Authentication
    user_id: str | None = None  # Owner of this agent
    team_id: str | None = None  # Team this agent belongs to

    # Capabilities (populated via MCP)
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskState:
    """State of a task in the system."""

    task_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    task_type: str = ""  # e.g., "code_generation", "code_review", "test_generation"

    # Assignment
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: str | None = None
    assigned_at: datetime | None = None

    # Execution
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: float = 0.0  # 0.0 to 1.0

    # Input/Output
    input_data: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None

    # Context
    user_id: str | None = None
    team_id: str | None = None
    parent_task_id: str | None = None  # For subtasks
    subtask_ids: list[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorState:
    """
    State for the LangGraph orchestrator.

    This is the shared state that flows through the orchestration graph.
    """

    # Current task being processed
    task: TaskState | None = None

    # Conversation/context
    messages: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    # Planning
    plan: list[dict[str, Any]] = field(default_factory=list)  # List of planned steps
    current_step: int = 0

    # Execution tracking
    agent_results: dict[str, Any] = field(default_factory=dict)  # agent_id -> result
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    # Available agents (populated at runtime)
    available_agents: list[AgentState] = field(default_factory=list)

    # Final output
    final_result: str | None = None
    error: str | None = None


@dataclass
class TeamState:
    """State of a team."""

    team_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str | None = None
    owner_id: str = ""  # User who created the team

    # Members
    member_ids: list[str] = field(default_factory=list)  # User IDs
    agent_ids: list[str] = field(default_factory=list)  # Agent IDs

    # Settings
    default_orchestrator_model: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None
