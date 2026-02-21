"""Pydantic schemas for GitHub ingestion API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ============== Normalized GitHub Data Types ==============


class GitHubPullRequest(BaseModel):
    """Normalized pull request data."""

    number: int
    title: str
    state: str  # open, closed, merged
    author: str
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None = None
    head_branch: str
    base_branch: str
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    labels: list[str] = Field(default_factory=list)
    has_conflicts: bool = False


class GitHubCommit(BaseModel):
    """Normalized commit data."""

    sha: str
    message: str
    author: str
    authored_at: datetime
    files_changed: int = 0


class GitHubCIStatus(BaseModel):
    """Normalized CI check status."""

    name: str
    status: str  # success, failure, pending, error
    conclusion: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    pr_number: int | None = None


# ============== API Request/Response Schemas ==============


class GitHubSyncRequest(BaseModel):
    """Request to trigger a GitHub sync for a project."""

    pass  # Project ID comes from path param


class GitHubSyncResponse(BaseModel):
    """Response after a GitHub sync completes."""

    project_id: str
    pull_requests_count: int
    commits_count: int
    ci_checks_count: int
    risks_created: int
    last_synced_at: datetime


class GitHubContextResponse(BaseModel):
    """Full GitHub context for a project."""

    id: str
    project_id: str
    pull_requests: list[dict[str, Any]]
    recent_commits: list[dict[str, Any]]
    ci_status: list[dict[str, Any]]
    last_synced_at: datetime | None
    sync_error: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
