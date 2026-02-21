"""SQLAlchemy database models."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.state import (
    AgentStatus,
    PlanStatus,
    PricingType,
    RiskSeverity,
    RiskSource,
    SubscriptionStatus,
    SubtaskStatus,
    TaskStatus,
    UserRole,
)
from src.storage.database import Base


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))

    # Profile
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="owner")
    owned_teams: Mapped[list["Team"]] = relationship("Team", back_populates="owner")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="owner")
    team_memberships: Mapped[list["TeamMember"]] = relationship("TeamMember", back_populates="user")


class Team(Base):
    """Team model for grouping users and agents."""

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Owner
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    owner: Mapped["User"] = relationship("User", back_populates="owned_teams")

    # Settings
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="team")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="team")


class Agent(Base):
    """Marketplace agent - hosted inference with built-in skills."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(100))  # coder, reviewer, designer, etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Inference config (seller provides)
    inference_endpoint: Mapped[str] = mapped_column(String(500))
    inference_api_key_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)
    inference_provider: Mapped[str] = mapped_column(String(50), default="openai")
    inference_model: Mapped[str] = mapped_column(String(100), default="gpt-4o-mini")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)  # Default system prompt

    # Skills this agent provides (built-in)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)

    status: Mapped[AgentStatus] = mapped_column(Enum(AgentStatus), default=AgentStatus.ONLINE)

    # Ownership
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    owner: Mapped["User"] = relationship("User", back_populates="agents")

    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True)
    team: Mapped["Team | None"] = relationship("Team", back_populates="agents")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Extra data (custom system prompt override, etc.)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="assigned_agent")
    allowed_projects: Mapped[list["ProjectAllowedAgent"]] = relationship(
        "ProjectAllowedAgent", back_populates="agent"
    )


class Task(Base):
    """Task model for tracking work items."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(100))  # code_generation, review, etc.

    # Status
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    progress: Mapped[float] = mapped_column(default=0.0)

    # Assignment
    assigned_agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agents.id"), nullable=True
    )
    assigned_agent: Mapped["Agent | None"] = relationship("Agent", back_populates="tasks")
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Team context
    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True)
    team: Mapped["Team | None"] = relationship("Team", back_populates="tasks")

    # User who created the task
    created_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Parent task (for subtasks)
    parent_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id"), nullable=True
    )

    # Input/Output
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Extra data
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships to subtasks
    subtasks: Mapped[list["Subtask"]] = relationship(
        "Subtask", back_populates="task", foreign_keys="Subtask.task_id"
    )


class Project(Base):
    """Project model for organizing work."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Project details
    goals: Mapped[list[str]] = mapped_column(JSON, default=list)
    milestones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    timeline: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # External references
    github_repo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Owner
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    owner: Mapped["User"] = relationship("User", back_populates="projects")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    plans: Mapped[list["Plan"]] = relationship("Plan", back_populates="project")
    team_members: Mapped[list["TeamMember"]] = relationship("TeamMember", back_populates="project")
    risk_signals: Mapped[list["RiskSignal"]] = relationship("RiskSignal", back_populates="project")
    allowed_agents: Mapped[list["ProjectAllowedAgent"]] = relationship(
        "ProjectAllowedAgent", back_populates="project", cascade="all, delete-orphan"
    )


class ProjectAllowedAgent(Base):
    """Project-level allowlist mapping for agents."""

    __tablename__ = "project_allowed_agents"
    __table_args__ = (UniqueConstraint("project_id", "agent_id", name="uq_project_allowed_agent"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    project: Mapped["Project"] = relationship("Project", back_populates="allowed_agents")

    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"))
    agent: Mapped["Agent"] = relationship("Agent", back_populates="allowed_projects")

    added_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Plan(Base):
    """Implementation plan requiring PM approval."""

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Task and project references
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    project: Mapped["Project"] = relationship("Project", back_populates="plans")

    # Plan content
    plan_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_plan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plans.id"), nullable=True
    )

    # Status and approval workflow
    status: Mapped[str] = mapped_column(String(50), default=PlanStatus.DRAFT.value)
    approved_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    subtasks: Mapped[list["Subtask"]] = relationship("Subtask", back_populates="plan")


class TeamMember(Base):
    """Team member assignment to a project with role and capacity."""

    __tablename__ = "team_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # User and project references
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    user: Mapped["User"] = relationship("User", back_populates="team_memberships")
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    project: Mapped["Project"] = relationship("Project", back_populates="team_members")

    # Role and capacity
    role: Mapped[str] = mapped_column(String(50), default=UserRole.DEVELOPER.value)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    capacity: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 to 1.0 availability
    current_load: Mapped[float] = mapped_column(Float, default=0.0)  # Current workload

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    assigned_subtasks: Mapped[list["Subtask"]] = relationship(
        "Subtask", back_populates="assignee", foreign_keys="Subtask.assignee_id"
    )


class Subtask(Base):
    """Subtask with draft status and local agent assignment."""

    __tablename__ = "subtasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Parent references
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"))
    task: Mapped["Task"] = relationship("Task", back_populates="subtasks", foreign_keys=[task_id])
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("plans.id"), nullable=True)
    plan: Mapped["Plan | None"] = relationship("Plan", back_populates="subtasks")

    # Subtask content
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(50), default=SubtaskStatus.PENDING.value)

    # Assignment
    assignee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("team_members.id"), nullable=True
    )
    assignee: Mapped["TeamMember | None"] = relationship(
        "TeamMember", back_populates="assigned_subtasks", foreign_keys=[assignee_id]
    )
    assigned_agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agents.id"), nullable=True
    )

    # Draft content (from local agent)
    draft_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    draft_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    draft_agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    draft_version: Mapped[int] = mapped_column(Integer, default=0)

    # Final content (after human edits)
    final_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Risk flags
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class RiskSignal(Base):
    """Risk signal from reviewer agent or automated checks."""

    __tablename__ = "risk_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Project reference
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))
    project: Mapped["Project"] = relationship("Project", back_populates="risk_signals")

    # Optional task/subtask reference
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True)
    subtask_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subtasks.id"), nullable=True
    )

    # Risk details
    source: Mapped[str] = mapped_column(String(50))  # RiskSource value
    severity: Mapped[str] = mapped_column(String(50))  # RiskSeverity value
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    is_resolved: Mapped[bool] = mapped_column(default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class AuditLog(Base):
    """Audit log for tracking important actions."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Actor
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True)

    # Action details
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(100))  # project, plan, task, subtask, etc.
    resource_id: Mapped[str] = mapped_column(String(36))

    # Context
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketplaceAgent(Base):
    """Agents listed for sale or free access on the marketplace."""

    __tablename__ = "marketplace_agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Core Agent Reference
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"))
    agent: Mapped["Agent"] = relationship("Agent")

    # Seller
    seller_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    seller: Mapped["User"] = relationship("User")

    # Listing Details
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100))  # coder, reviewer, etc

    # Pricing & Billing
    pricing_type: Mapped[str] = mapped_column(String(50), default=PricingType.FREE.value)
    price_per_use: Mapped[float | None] = mapped_column(Float, nullable=True)

    paid_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status
    is_verified: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class SellerProfile(Base):
    """Profile for users who sell agents on the marketplace."""

    __tablename__ = "seller_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True)
    user: Mapped["User"] = relationship("User")

    stripe_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payout_enabled: Mapped[bool] = mapped_column(default=False)

    total_earnings: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class AgentSubscription(Base):
    """Tracks a team's subscription to a marketplace agent."""

    __tablename__ = "agent_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("teams.id"))
    team: Mapped["Team"] = relationship("Team")

    marketplace_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("marketplace_agents.id")
    )
    marketplace_agent: Mapped["MarketplaceAgent"] = relationship("MarketplaceAgent")

    status: Mapped[str] = mapped_column(String(50), default=SubscriptionStatus.ACTIVE.value)

    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paid_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GitHubContext(Base):
    """Cached GitHub data for a project (PRs, commits, CI status)."""

    __tablename__ = "github_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Project reference
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), unique=True)
    project: Mapped["Project"] = relationship("Project")

    # Cached GitHub data
    pull_requests: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    recent_commits: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    ci_status: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # Sync metadata
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class UsageRecord(Base):
    """Tracks agent usage for billing purposes."""

    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("teams.id"))
    team: Mapped["Team"] = relationship("Team")

    marketplace_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("marketplace_agents.id")
    )
    marketplace_agent: Mapped["MarketplaceAgent"] = relationship("MarketplaceAgent")

    usage_type: Mapped[str] = mapped_column(String(100))  # tool_call, task_completion
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    cost: Mapped[float] = mapped_column(Float, default=0.0)

    paid_signal_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
