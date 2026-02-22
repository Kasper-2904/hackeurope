"""
LangGraph-based orchestrator for delegating tasks to agents.

The orchestrator:
1. Receives tasks from the API
2. Analyzes the task and creates a plan
3. Routes tasks to appropriate agents based on their skills
4. Manages the execution flow
5. Aggregates results
"""

import json
import logging
import litellm
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import AgentStatus, TaskStatus
from src.services.agent_inference import get_inference_service
from src.storage.database import AsyncSessionLocal as async_session_factory
from src.storage.models import Agent

logger = logging.getLogger(__name__)


class OrchestratorState(TypedDict, total=False):
    """State that flows through the orchestration graph."""

    # Task information
    task_id: str
    task_type: str
    task_description: str
    input_data: dict[str, Any]

    # Planning
    plan: list[dict[str, Any]]  # List of steps
    current_step: int

    # Execution
    selected_agent_id: str | None
    skill_name: str | None
    skill_inputs: dict[str, Any]

    # Results
    step_results: list[dict[str, Any]]
    final_result: str | None
    error: str | None

    # Status
    status: str  # pending, planning, executing, completed, failed

    # Context
    user_id: str | None
    team_id: str | None
    subtask_id: str | None
    project_id: str | None
    shared_context: str | None  # Rendered shared context injected before planning


async def _load_shared_context(project_id: str | None) -> str:
    """Sync GitHub data (if stale) and load shared context for a project.

    Checks if GitHub context is fresh (synced within 5 min TTL).
    If stale, triggers a fresh sync. Then gathers all shared context
    (project info, GitHub PRs/commits/CI, tasks, risks, team, agents)
    and renders it as a single markdown string for the LLM prompt.
    """
    if not project_id:
        return ""

    try:
        from datetime import timezone

        from src.services.context_service import SharedContextService
        from src.services.github_service import GitHubService
        from src.storage.models import GitHubContext

        async with async_session_factory() as session:
            # Check if context is fresh (synced within last 5 minutes)
            ctx_result = await session.execute(
                select(GitHubContext).where(GitHubContext.project_id == project_id)
            )
            existing_ctx = ctx_result.scalar_one_or_none()
            needs_sync = True
            if existing_ctx and existing_ctx.last_synced_at:
                age = (datetime.now(timezone.utc) - existing_ctx.last_synced_at).total_seconds()
                if age < 300:  # 5 minute TTL
                    needs_sync = False
                    logger.info("Skipping GitHub sync — context is %ds old (TTL 300s)", int(age))

            if needs_sync:
                github_service = GitHubService()
                try:
                    await github_service.sync_project(project_id, session)
                except Exception as e:
                    logger.warning("GitHub sync failed during context load: %s", e)

            # Gather full shared context from DB + refreshed MD files
            context_service = SharedContextService()
            ctx = await context_service.gather_context(project_id, session)

        # Render context dict into a single markdown block for the prompt
        parts = []
        for key in ("project_overview", "integrations_github", "task_graph",
                     "team_members", "hosted_agents"):
            content = ctx.get(key, "")
            if content and content.strip():
                parts.append(content.strip())

        # Add live DB risk signals
        risks = ctx.get("open_risks", [])
        if risks:
            risk_lines = [f"- [{r['severity']}] {r['title']}: {r['description']}" for r in risks]
            parts.append("# Open Risk Signals\n" + "\n".join(risk_lines))

        return "\n\n---\n\n".join(parts) if parts else ""
    except Exception as e:
        logger.warning("Failed to load shared context for project %s: %s", project_id, e)
        return ""


async def analyze_task(state: OrchestratorState) -> OrchestratorState:
    """Analyze the task and create a plan using LLM."""
    event_bus = get_event_bus()

    task_type = state.get("task_type", "")
    description = state.get("task_description", "")
    project_id = state.get("project_id")

    settings = get_settings()

    await event_bus.publish(
        Event(
            type=EventType.TASK_STARTED,
            data={
                "task_id": state.get("task_id"),
                "task_type": task_type,
            },
            source="orchestrator",
        )
    )

    # Load shared context (triggers GitHub sync + context refresh)
    shared_context = await _load_shared_context(project_id)
    context_block = ""
    if shared_context:
        context_block = f"""

    === PROJECT CONTEXT ===
    {shared_context}
    === END PROJECT CONTEXT ===
    """

    prompt = f"""
    You are an orchestration agent. Analyze this task and break it down into skills to execute.
    {context_block}
    Task Type: {task_type}
    Description: {description}

    Available skills: generate_code, review_code, debug_code, refactor_code, explain_code,
    check_security, suggest_improvements, design_component

    Respond ONLY with a JSON array of skill names in execution order.
    Example: ["generate_code"]
    """

    try:
        response = await litellm.acompletion(
            model=settings.default_llm_model,
            messages=[{"role": "user", "content": prompt}],
            api_key=settings.anthropic_api_key,
        )

        content = response.choices[0].message.content or "[]"

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        plan = json.loads(content.strip())

        if not isinstance(plan, list):
            plan = [plan]

        plan = [{"skill": s, "status": "pending"} for s in plan if isinstance(s, str)]

    except Exception as e:
        # Fallback plan based on task type
        task_to_skills = {
            "code_generation": [{"skill": "generate_code", "status": "pending"}],
            "code_review": [{"skill": "review_code", "status": "pending"}],
            "bug_fix": [
                {"skill": "debug_code", "status": "pending"},
                {"skill": "generate_code", "status": "pending"},
            ],
            "refactor": [{"skill": "refactor_code", "status": "pending"}],
            "security_audit": [{"skill": "check_security", "status": "pending"}],
            "documentation": [{"skill": "generate_code", "status": "pending"}],
        }
        plan = task_to_skills.get(task_type, [{"skill": "generate_code", "status": "pending"}])

    return {
        **state,
        "plan": plan,
        "current_step": 0,
        "step_results": [],
        "status": "planning",
        "shared_context": shared_context,
    }


async def select_agent(state: OrchestratorState) -> OrchestratorState:
    """Select the best agent for the current step based on skills."""
    event_bus = get_event_bus()

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if current_step >= len(plan):
        return {**state, "selected_agent_id": None}

    step = plan[current_step]
    required_skill = step.get("skill", "")

    team_id = state.get("team_id")

    # Query agents from database
    async with async_session_factory() as session:
        query = select(Agent).where(Agent.status == AgentStatus.ONLINE)

        result = await session.execute(query)
        agents = list(result.scalars().all())

        # Filter by skill
        agents_with_skill = [a for a in agents if required_skill in (a.skills or [])]

        if agents_with_skill:
            selected = agents_with_skill[0]
        elif agents:
            selected = agents[0]
        else:
            selected = None

    if not selected:
        await event_bus.publish(
            Event(
                type=EventType.SYSTEM_WARNING,
                data={
                    "task_id": state.get("task_id"),
                    "message": f"No agents available for skill: {required_skill}",
                },
                source="orchestrator",
            )
        )
        return {
            **state,
            "selected_agent_id": None,
            "error": f"No agents available for skill: {required_skill}",
            "status": "failed",
        }

    await event_bus.publish(
        Event(
            type=EventType.TASK_ASSIGNED,
            data={
                "task_id": state.get("task_id"),
                "agent_id": selected.id,
                "skill": required_skill,
            },
            source="orchestrator",
            target=selected.id,
        )
    )

    return {
        **state,
        "selected_agent_id": selected.id,
        "skill_name": required_skill,
        "status": "executing",
    }


async def execute_skill(state: OrchestratorState) -> OrchestratorState:
    """Execute the skill on the selected agent."""
    event_bus = get_event_bus()
    inference_service = get_inference_service()

    agent_id = state.get("selected_agent_id")
    skill_name = state.get("skill_name")
    input_data = state.get("input_data", {})

    if not agent_id or not skill_name:
        return {
            **state,
            "error": "No agent or skill selected",
            "status": "failed",
        }

    # Get agent from database
    async with async_session_factory() as session:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            return {
                **state,
                "error": f"Agent {agent_id} not found",
                "status": "failed",
            }

        # Prepare skill inputs — merge task_description into input_data
        enriched_input = {**input_data, "description": state.get("task_description", "")}
        skill_inputs = _prepare_skill_inputs(skill_name, enriched_input)

        # Build system prompt with shared context for the specialist agent
        base_prompt = agent.system_prompt or ""
        shared_ctx = state.get("shared_context", "")
        if shared_ctx:
            system_prompt = (
                f"{base_prompt}\n\n"
                f"=== PROJECT CONTEXT ===\n"
                f"{shared_ctx}\n"
                f"=== END PROJECT CONTEXT ==="
            ) if base_prompt else shared_ctx
        else:
            system_prompt = base_prompt or None

        # Execute skill via inference service
        result_text, _token_usage = await inference_service.execute_skill(
            agent=agent,
            skill=skill_name,
            inputs=skill_inputs,
            system_prompt=system_prompt,
        )

    # Record the result
    step_results = state.get("step_results", [])
    step_results.append(
        {
            "step": state.get("current_step", 0) + 1,
            "agent_id": agent_id,
            "skill": skill_name,
            "inputs": skill_inputs,
            "result": result_text,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    # Update plan status
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    if current_step < len(plan):
        plan[current_step]["status"] = "completed"
        plan[current_step]["result"] = result_text

    await event_bus.publish(
        Event(
            type=EventType.TASK_PROGRESS,
            data={
                "task_id": state.get("task_id"),
                "step": current_step + 1,
                "total_steps": len(plan),
                "result": result_text,
            },
            source="orchestrator",
        )
    )

    return {
        **state,
        "plan": plan,
        "step_results": step_results,
        "current_step": current_step + 1,
    }


async def aggregate_results(state: OrchestratorState) -> OrchestratorState:
    """Aggregate results from all steps."""
    event_bus = get_event_bus()

    step_results = state.get("step_results", [])

    # Combine all results
    final_parts = []
    for result in step_results:
        skill = result.get("skill", "unknown")
        skill_result = result.get("result", "")
        final_parts.append(f"## {skill}\n{skill_result}")

    final_result = "\n\n".join(final_parts) if final_parts else "No results generated."

    # Check if any step failed
    has_errors = any(r.get("error") for r in step_results)

    status = "completed" if not has_errors else "completed_with_errors"

    await event_bus.publish(
        Event(
            type=EventType.TASK_COMPLETED,
            data={
                "task_id": state.get("task_id"),
                "subtask_id": state.get("subtask_id"),
                "status": status,
                "step_count": len(step_results),
                "handoff_required": True,
            },
            source="orchestrator",
        )
    )

    return {
        **state,
        "final_result": final_result,
        "status": status,
    }


def _prepare_skill_inputs(skill_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
    """Prepare inputs for a skill based on the skill name and input data."""
    description = input_data.get("description", "")

    if skill_name == "generate_code":
        return {
            "task": description,
            "language": input_data.get("language", "python"),
        }

    if skill_name == "review_code":
        return {
            "code": input_data.get("code", ""),
            "task": description,
        }

    if skill_name == "debug_code":
        return {
            "code": input_data.get("code", ""),
            "error": input_data.get("error", ""),
            "task": description,
        }

    if skill_name == "refactor_code":
        return {
            "code": input_data.get("code", ""),
            "instructions": input_data.get("instructions", "") or description,
        }

    # Default: pass everything including description
    return input_data


def should_continue(state: OrchestratorState) -> Literal["select_agent", "aggregate"]:
    """Determine if we should continue executing or aggregate results."""
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    status = state.get("status", "")

    if status == "failed":
        return "aggregate"

    if current_step >= len(plan):
        return "aggregate"

    return "select_agent"


def check_agent_selection(state: OrchestratorState) -> Literal["execute", "aggregate"]:
    """Check if agent selection was successful."""
    if state.get("selected_agent_id") is None:
        return "aggregate"
    return "execute"


def build_orchestrator_graph() -> StateGraph:
    """Build the LangGraph orchestration graph."""
    graph = StateGraph(OrchestratorState)

    graph.add_node("analyze_task", analyze_task)
    graph.add_node("select_agent", select_agent)
    graph.add_node("execute_skill", execute_skill)
    graph.add_node("aggregate_results", aggregate_results)

    graph.set_entry_point("analyze_task")
    graph.add_edge("analyze_task", "select_agent")

    graph.add_conditional_edges(
        "select_agent",
        check_agent_selection,
        {
            "execute": "execute_skill",
            "aggregate": "aggregate_results",
        },
    )

    graph.add_conditional_edges(
        "execute_skill",
        should_continue,
        {
            "select_agent": "select_agent",
            "aggregate": "aggregate_results",
        },
    )

    graph.add_edge("aggregate_results", END)

    return graph


class Orchestrator:
    """Main orchestrator class that manages task execution."""

    def __init__(self):
        self._graph = build_orchestrator_graph()
        self._compiled = self._graph.compile()

    async def execute_task(
        self,
        task_id: str,
        task_type: str,
        description: str,
        input_data: dict[str, Any] | None = None,
        team_id: str | None = None,
        user_id: str | None = None,
        subtask_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a task through the orchestration pipeline."""
        initial_state: OrchestratorState = {
            "task_id": task_id,
            "task_type": task_type,
            "task_description": description,
            "input_data": input_data or {},
            "plan": [],
            "current_step": 0,
            "selected_agent_id": None,
            "skill_name": None,
            "skill_inputs": {},
            "step_results": [],
            "final_result": None,
            "error": None,
            "status": "pending",
            "team_id": team_id,
            "user_id": user_id,
            "subtask_id": subtask_id,
            "project_id": project_id,
            "shared_context": None,
        }

        final_state = await self._compiled.ainvoke(initial_state)

        return {
            "task_id": task_id,
            "status": final_state.get("status"),
            "result": final_state.get("final_result"),
            "error": final_state.get("error"),
            "steps": final_state.get("step_results"),
            "plan": final_state.get("plan"),
        }


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
