"""SQLAlchemy database models."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.state import AgentStatus, TaskStatus
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
    """Agent model for registered MCP servers."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(100))  # coder, reviewer, tester, etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Connection
    mcp_endpoint: Mapped[str] = mapped_column(String(500))  # URL to agent's MCP server
    status: Mapped[AgentStatus] = mapped_column(Enum(AgentStatus), default=AgentStatus.PENDING)

    # Authentication token for this agent
    api_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Ownership
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    owner: Mapped["User"] = relationship("User", back_populates="agents")

    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True)
    team: Mapped["Team | None"] = relationship("Team", back_populates="agents")

    # Capabilities (cached from MCP discovery)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Extra data
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="assigned_agent")


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
