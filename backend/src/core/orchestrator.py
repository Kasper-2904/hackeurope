"""
LangGraph-based orchestrator for planning tasks using Claude and shared context.

The orchestrator:
1. Gathers shared context (markdown files + live DB data)
2. Calls Claude to generate an implementation plan
3. Persists the plan to the database
"""

import json
from datetime import datetime
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import PlanStatus
from src.services.context_service import SharedContextService
from src.services.llm_service import LLMService, get_llm_service
from src.storage.models import Plan


# ============== State ==============


class OrchestratorState(TypedDict, total=False):
    """State that flows through the orchestration graph."""

    # Input
    task_id: str
    task_title: str
    task_description: str
    project_id: str
    db: Any  # AsyncSession (not serializable, passed through state)

    # Context
    shared_context: dict[str, Any]

    # Plan output
    plan_data: dict[str, Any]
    plan_id: str | None
    rationale: str | None

    # Status
    status: str  # pending, gathering_context, planning, persisted, failed
    error: str | None

    # Context
    user_id: str | None
    team_id: str | None
    subtask_id: str | None


# ============== Node Functions ==============


async def gather_context(state: OrchestratorState) -> OrchestratorState:
    """Read shared context files and enrich with DB data."""
    event_bus = get_event_bus()
    project_id = state.get("project_id", "")
    db: AsyncSession = state["db"]

    await event_bus.publish(
        Event(
            type=EventType.TASK_STARTED,
            data={
                "task_id": state.get("task_id"),
                "phase": "gather_context",
            },
            source="orchestrator",
        )
    )

    context_service = SharedContextService()
    shared_context = await context_service.gather_context(project_id, db)

    return {
        **state,
        "shared_context": shared_context,
        "status": "gathering_context",
    }


async def generate_plan(state: OrchestratorState) -> OrchestratorState:
    """Call Claude to generate an implementation plan from context + task."""
    event_bus = get_event_bus()
    llm: LLMService = get_llm_service()

    task_title = state.get("task_title", "")
    task_description = state.get("task_description", "")
    shared_context = state.get("shared_context", {})

    # Build context summary for the prompt
    context_summary = _build_context_summary(shared_context)

    system_prompt = (
        "You are the Orchestration Agent (OA) for a software delivery platform. "
        "Given a task and project context, generate an implementation plan.\n\n"
        "Your plan must include:\n"
        "1. A list of subtasks with titles and descriptions\n"
        "2. For each subtask, a suggested specialist agent type (coder, reviewer, tester, docs)\n"
        "3. A suggested team member assignment (by role: developer or pm)\n"
        "4. Risk flags if any\n"
        "5. A short rationale explaining your approach\n\n"
        "Respond in JSON with this structure:\n"
        "{\n"
        '  "subtasks": [\n'
        '    {"title": "...", "description": "...", "agent_type": "...", '
        '"assignee_role": "developer", "priority": 1, "risk_flags": []}\n'
        "  ],\n"
        '  "rationale": "..."\n'
        "}"
    )

    user_message = (
        f"## Task\n**{task_title}**\n{task_description}\n\n"
        f"## Project Context\n{context_summary}"
    )

    await event_bus.publish(
        Event(
            type=EventType.TASK_PROGRESS,
            data={
                "task_id": state.get("task_id"),
                "phase": "generate_plan",
                "message": "Calling Claude to generate plan...",
            },
            source="orchestrator",
        )
    )

    try:
        plan_data = await llm.complete_json(
            system=system_prompt,
            user_message=user_message,
        )
    except Exception as e:
        return {
            **state,
            "plan_data": {},
            "error": f"LLM call failed: {e}",
            "status": "failed",
        }

    # Validate minimum structure
    if "subtasks" not in plan_data:
        return {
            **state,
            "plan_data": plan_data,
            "error": "LLM response missing 'subtasks' key",
            "status": "failed",
        }

    return {
        **state,
        "plan_data": plan_data,
        "rationale": plan_data.get("rationale", ""),
        "status": "planning",
    }


async def persist_plan(state: OrchestratorState) -> OrchestratorState:
    """Save the generated plan to the database as a draft."""
    event_bus = get_event_bus()
    db: AsyncSession = state["db"]

    plan_data = state.get("plan_data", {})
    if not plan_data or state.get("status") == "failed":
        return state

    plan_id = str(uuid4())
    plan = Plan(
        id=plan_id,
        task_id=state["task_id"],
        project_id=state["project_id"],
        plan_data=plan_data,
        rationale=state.get("rationale"),
        status=PlanStatus.DRAFT.value,
    )
    db.add(plan)
    await db.flush()

    await event_bus.publish(
        Event(
            type=EventType.TASK_COMPLETED,
            data={
                "task_id": state.get("task_id"),
                "plan_id": plan_id,
                "subtask_count": len(plan_data.get("subtasks", [])),
            },
            source="orchestrator",
        )
    )

    return {
        **state,
        "plan_id": plan_id,
        "status": "persisted",
    }


# ============== Helpers ==============


def _build_context_summary(ctx: dict[str, Any]) -> str:
    """Build a readable text summary from shared context for the LLM prompt."""
    parts = []

    # Project info
    project = ctx.get("project", {})
    if project:
        parts.append(f"**Project:** {project.get('name', 'N/A')}")
        if project.get("description"):
            parts.append(f"Description: {project['description']}")
        if project.get("goals"):
            parts.append(f"Goals: {', '.join(project['goals'])}")

    # Team
    members = ctx.get("team_members_db", [])
    if members:
        member_lines = [
            f"- {m['role']}: skills={m['skills']}, capacity={m['capacity']}"
            for m in members
        ]
        parts.append(f"**Team ({len(members)} members):**\n" + "\n".join(member_lines))

    # Existing tasks
    tasks = ctx.get("tasks_db", [])
    if tasks:
        task_lines = [f"- [{t['status']}] {t['title']}" for t in tasks]
        parts.append(f"**Existing Tasks ({len(tasks)}):**\n" + "\n".join(task_lines))

    # GitHub
    gh = ctx.get("github_context", {})
    if gh:
        prs = gh.get("pull_requests", [])
        if prs:
            parts.append(f"**Open PRs:** {len(prs)}")
        ci = gh.get("ci_status", [])
        failures = [c for c in ci if c.get("conclusion") == "failure"]
        if failures:
            parts.append(f"**CI Failures:** {len(failures)}")

    # Risks
    risks = ctx.get("open_risks", [])
    if risks:
        risk_lines = [f"- [{r['severity']}] {r['title']}" for r in risks]
        parts.append(f"**Open Risks ({len(risks)}):**\n" + "\n".join(risk_lines))

    # Static context snippets (only include non-empty)
    for key in ("project_overview", "project_plan", "task_graph"):
        content = ctx.get(key, "").strip()
        if content and len(content) > 50:  # Skip empty templates
            parts.append(f"**{key}:**\n{content[:2000]}")

    return "\n\n".join(parts) if parts else "No project context available."


# ============== Routing ==============


def check_plan_status(state: OrchestratorState) -> Literal["persist", "end"]:
    """Route based on whether planning succeeded."""
    if state.get("status") == "failed":
        return "end"
    return "persist"


# ============== Graph Builder ==============


def build_orchestrator_graph() -> StateGraph:
    """
    Build the LangGraph orchestration graph.

    Flow:
    START -> gather_context -> generate_plan -> persist_plan -> END
                                    |
                               (if failed) -> END
    """
    graph = StateGraph(OrchestratorState)

    graph.add_node("gather_context", gather_context)
    graph.add_node("generate_plan", generate_plan)
    graph.add_node("persist_plan", persist_plan)

    graph.set_entry_point("gather_context")
    graph.add_edge("gather_context", "generate_plan")

    graph.add_conditional_edges(
        "generate_plan",
        check_plan_status,
        {
            "persist": "persist_plan",
            "end": END,
        },
    )

    graph.add_edge("persist_plan", END)

    return graph


# ============== Orchestrator Class ==============


class Orchestrator:
    """Main orchestrator — generates Claude-powered implementation plans."""

    def __init__(self):
        self._graph = build_orchestrator_graph()
        self._compiled = self._graph.compile()

    async def generate_plan(
        self,
        *,
        task_id: str,
        task_title: str,
        task_description: str,
        project_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Generate an implementation plan for a task.

        Returns:
            Dict with plan_id, status, plan_data, rationale, error.
        """
        initial_state: OrchestratorState = {
            "task_id": task_id,
            "task_title": task_title,
            "task_description": task_description,
            "project_id": project_id,
            "db": db,
            "shared_context": {},
            "plan_data": {},
            "plan_id": None,
            "rationale": None,
            "status": "pending",
            "error": None,
        }

        final_state = await self._compiled.ainvoke(initial_state)

        return {
            "task_id": task_id,
            "plan_id": final_state.get("plan_id"),
            "status": final_state.get("status"),
            "plan_data": final_state.get("plan_data"),
            "rationale": final_state.get("rationale"),
            "error": final_state.get("error"),
        }


# Global orchestrator instance
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
