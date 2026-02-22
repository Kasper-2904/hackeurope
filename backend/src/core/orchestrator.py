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
from uuid import uuid4

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import AgentStatus, TaskStatus
from src.services.agent_inference import get_inference_service
from src.storage.database import AsyncSessionLocal as async_session_factory
from src.core.state import PlanStatus
from src.storage.models import Agent, Plan, ProjectAllowedAgent, Task, TaskLog, TeamMember

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
    agent_selection_log: list[dict[str, Any]]
    final_result: str | None
    error: str | None

    # Status
    status: str  # pending, planning, executing, completed, failed

    # Context
    user_id: str | None
    team_id: str | None
    subtask_id: str | None
    project_id: str | None  # Project ID for agent allowlist filtering
    shared_context: str | None  # Rendered shared context injected before planning


async def log_task_activity(
    task_id: str,
    log_type: str,
    message: str,
    agent_id: str | None = None,
    agent_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Create a task log entry for real-time activity streaming."""
    from uuid import uuid4

    async with async_session_factory() as session:
        # Get next sequence number
        result = await session.execute(
            select(TaskLog.sequence)
            .where(TaskLog.task_id == task_id)
            .order_by(TaskLog.sequence.desc())
            .limit(1)
        )
        last_seq = result.scalar_one_or_none()
        next_seq = (last_seq or 0) + 1

        log = TaskLog(
            id=str(uuid4()),
            task_id=task_id,
            log_type=log_type,
            agent_id=agent_id,
            agent_name=agent_name,
            message=message,
            details=details,
            sequence=next_seq,
        )
        session.add(log)
        await session.commit()


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
        for key in (
            "project_overview",
            "integrations_github",
            "task_graph",
            "team_members",
            "hosted_agents",
        ):
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
    task_id = state.get("task_id", "")

    settings = get_settings()

    # Log task analysis started
    await log_task_activity(
        task_id=task_id,
        log_type="info",
        message=f"Analyzing task: {task_type}",
        details={"description": description[:200] if description else None},
    )

    await event_bus.publish(
        Event(
            type=EventType.TASK_STARTED,
            data={
                "task_id": task_id,
                "task_type": task_type,
                "message": "Task execution started",
                "status": "in_progress",
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

    # Log the created plan
    skills_list = [s.get("skill", "") for s in plan]
    await log_task_activity(
        task_id=task_id,
        log_type="info",
        message=f"Created execution plan with {len(plan)} step(s): {', '.join(skills_list)}",
        details={"plan": plan},
    )

    return {
        **state,
        "plan": plan,
        "current_step": 0,
        "step_results": [],
        "status": "planning",
        "shared_context": shared_context,
    }


async def select_agent(state: OrchestratorState) -> OrchestratorState:
    """Select the best agent for the current step based on skills and project allowlist."""
    event_bus = get_event_bus()

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    selection_log = list(state.get("agent_selection_log", []))

    if current_step >= len(plan):
        return {**state, "selected_agent_id": None}

    step = plan[current_step]
    required_skill = step.get("skill", "")

    team_id = state.get("team_id")
    project_id = state.get("project_id")

    # Query agents from database
    async with async_session_factory() as session:
        # If project_id is provided, filter by project allowlist first
        if project_id:
            # Get allowed agent IDs for this project
            allowlist_result = await session.execute(
                select(ProjectAllowedAgent.agent_id).where(
                    ProjectAllowedAgent.project_id == project_id
                )
            )
            allowed_agent_ids = [row[0] for row in allowlist_result.fetchall()]

            if allowed_agent_ids:
                # Query only allowed agents that are online
                query = select(Agent).where(
                    Agent.status == AgentStatus.ONLINE,
                    Agent.id.in_(allowed_agent_ids),
                )
            else:
                # No allowlist defined, fall back to all online agents
                query = select(Agent).where(Agent.status == AgentStatus.ONLINE)
        else:
            # No project context, use all online agents
            query = select(Agent).where(Agent.status == AgentStatus.ONLINE)

        result = await session.execute(query)
        agents = list(result.scalars().all())

        # Filter by skill
        agents_with_skill = [a for a in agents if required_skill in (a.skills or [])]

        if agents_with_skill:
            selected = agents_with_skill[0]
            reason = f"Agent '{selected.name}' has the required skill '{required_skill}'."
        elif agents:
            # Fall back to any available agent if no skill match
            selected = agents[0]
            reason = (
                f"No agent matched skill '{required_skill}'; falling back to '{selected.name}'."
            )
        else:
            selected = None
            reason = f"No online agents available for skill '{required_skill}'."

    # Log the selection decision
    log_entry = {
        "step": current_step,
        "required_skill": required_skill,
        "candidates": [{"id": a.id, "name": a.name, "skills": a.skills or []} for a in agents],
        "skill_matches": [{"id": a.id, "name": a.name} for a in agents_with_skill],
        "selected": {"id": selected.id, "name": selected.name} if selected else None,
        "reason": reason,
    }
    selection_log.append(log_entry)

    if not selected:
        error_msg = f"No agents available for skill: {required_skill}"
        if project_id:
            error_msg += f" (filtered by project allowlist)"

        await event_bus.publish(
            Event(
                type=EventType.TASK_FAILED,
                data={
                    "task_id": state.get("task_id"),
                    "subtask_id": state.get("subtask_id"),
                    "message": error_msg,
                    "status": "failed",
                },
                source="orchestrator",
            )
        )
        await event_bus.publish(
            Event(
                type=EventType.SYSTEM_WARNING,
                data={
                    "task_id": state.get("task_id"),
                    "message": error_msg,
                },
                source="orchestrator",
            )
        )
        return {
            **state,
            "selected_agent_id": None,
            "agent_selection_log": selection_log,
            "error": error_msg,
            "status": "failed",
        }

    # Update the Task in the database with the assigned agent
    task_id = state.get("task_id")
    if task_id:
        async with async_session_factory() as session:
            task_result = await session.execute(select(Task).where(Task.id == task_id))
            task = task_result.scalar_one_or_none()
            if task:
                from datetime import datetime

                task.assigned_agent_id = selected.id
                task.assigned_at = datetime.utcnow()
                task.status = TaskStatus.ASSIGNED
                await session.commit()

    # Log agent assignment
    if task_id:
        await log_task_activity(
            task_id=task_id,
            log_type="agent_assigned",
            message=f"Assigned to agent: {selected.name} ({selected.role})",
            agent_id=selected.id,
            agent_name=selected.name,
            details={"skill": required_skill, "agent_role": selected.role},
        )

    await event_bus.publish(
        Event(
            type=EventType.TASK_ASSIGNED,
            data={
                "task_id": state.get("task_id"),
                "agent_id": selected.id,
                "agent_name": selected.name,
                "skill": required_skill,
                "reason": reason,
                "message": f"Assigned {required_skill} to agent {selected.id}",
                "status": "in_progress",
            },
            source="orchestrator",
            target=selected.id,
        )
    )

    return {
        **state,
        "selected_agent_id": selected.id,
        "skill_name": required_skill,
        "agent_selection_log": selection_log,
        "status": "executing",
    }


async def execute_skill(state: OrchestratorState) -> OrchestratorState:
    """Execute the skill on the selected agent."""
    event_bus = get_event_bus()
    inference_service = get_inference_service()

    agent_id = state.get("selected_agent_id")
    skill_name = state.get("skill_name")
    input_data = state.get("input_data", {})
    task_id = state.get("task_id", "")

    if not agent_id or not skill_name:
        message = "No agent or skill selected"
        await event_bus.publish(
            Event(
                type=EventType.TASK_FAILED,
                data={
                    "task_id": state.get("task_id"),
                    "subtask_id": state.get("subtask_id"),
                    "message": message,
                    "status": "failed",
                },
                source="orchestrator",
            )
        )
        return {
            **state,
            "error": message,
            "status": "failed",
        }

    # Get agent from database first for logging
    async with async_session_factory() as session:
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

    if not agent:
        error_msg = f"Agent {agent_id} not found"
        if task_id:
            await log_task_activity(
                task_id=task_id,
                log_type="error",
                message=error_msg,
                agent_id=agent_id,
                details={"skill": skill_name},
            )
        await event_bus.publish(
            Event(
                type=EventType.TASK_FAILED,
                data={
                    "task_id": state.get("task_id"),
                    "subtask_id": state.get("subtask_id"),
                    "message": error_msg,
                    "status": "failed",
                },
                source="orchestrator",
            )
        )
        return {
            **state,
            "error": error_msg,
            "status": "failed",
        }

    # Log skill execution start with agent name
    if task_id:
        await log_task_activity(
            task_id=task_id,
            log_type="skill_start",
            message=f"Agent '{agent.name}' executing skill: {skill_name}",
            agent_id=agent_id,
            agent_name=agent.name,
            details={"skill": skill_name, "agent_role": agent.role},
        )

    # Prepare skill inputs — merge task_description into input_data
    enriched_input = {**input_data, "description": state.get("task_description", "")}
    skill_inputs = _prepare_skill_inputs(skill_name, enriched_input)

    # Build system prompt with shared context for the specialist agent
    base_prompt = agent.system_prompt or ""
    shared_ctx = state.get("shared_context", "")
    if shared_ctx:
        system_prompt = (
            (f"{base_prompt}\n\n=== PROJECT CONTEXT ===\n{shared_ctx}\n=== END PROJECT CONTEXT ===")
            if base_prompt
            else shared_ctx
        )
    else:
        system_prompt = base_prompt or None

    # Execute skill via inference service with error handling
    try:
        result_text, _token_usage = await inference_service.execute_skill(
            agent=agent,
            skill=skill_name,
            inputs=skill_inputs,
            system_prompt=system_prompt,
        )
    except Exception as e:
        error_msg = f"Error calling agent '{agent.name}': {str(e)}"
        if task_id:
            await log_task_activity(
                task_id=task_id,
                log_type="error",
                message=error_msg,
                agent_id=agent_id,
                agent_name=agent.name,
                details={"skill": skill_name, "error": str(e)},
            )
        return {
            **state,
            "error": error_msg,
            "status": "failed",
            "step_results": state.get("step_results", [])
            + [
                {
                    "step": state.get("current_step", 0) + 1,
                    "agent_id": agent_id,
                    "skill": skill_name,
                    "inputs": skill_inputs,
                    "result": None,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }

    agent_name = agent.name

    # Log agent output
    if task_id:
        await log_task_activity(
            task_id=task_id,
            log_type="agent_output",
            message=result_text[:500] if result_text else "No output",
            agent_id=agent_id,
            agent_name=agent_name,
            details={
                "skill": skill_name,
                "full_output": result_text,
            },
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
                "task_id": task_id,
                "step": current_step + 1,
                "total_steps": len(plan),
                "summary": f"Completed step {current_step + 1} of {len(plan)} ({skill_name})",
                "status": "in_progress",
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

    # Preserve failed status if already set, otherwise check for errors
    existing_status = state.get("status", "")
    if existing_status == "failed":
        status = "failed"
        final_result = state.get("error", "Task failed")
    else:
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
                "message": "Task execution completed",
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
        """Execute a task through the orchestration pipeline.

        Args:
            task_id: The task ID
            task_type: Type of task (code_generation, review, etc.)
            description: Task description
            input_data: Additional input data for the task
            team_id: Team context (optional)
            user_id: User who triggered the task (optional)
            subtask_id: Subtask ID if this is a subtask (optional)
            project_id: Project ID for filtering agents by allowlist (optional)
        """
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
            "agent_selection_log": [],
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
            "agent_selection_log": final_state.get("agent_selection_log", []),
        }

    async def generate_plan(
        self,
        task_id: str,
        task_title: str,
        task_description: str,
        project_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Generate a plan with OA reasoning and persist it to the database."""
        logger = logging.getLogger(__name__)
        settings = get_settings()

        # Query available agents to provide real context to the LLM
        result = await db.execute(select(Agent).where(Agent.status == AgentStatus.ONLINE))
        agents = list(result.scalars().all())

        agent_descriptions = "\n".join(
            f"- {a.name} (role: {a.role}, skills: {', '.join(a.skills or [])}): {a.description or 'No description'}"
            for a in agents
        )

        # Query team members for assignee suggestions
        tm_result = await db.execute(select(TeamMember).where(TeamMember.project_id == project_id))
        members = list(tm_result.scalars().all())

        member_descriptions = (
            "\n".join(
                f"- Member {m.user_id[:8]} (role: {m.role}, skills: {', '.join(m.skills or [])}, capacity: {m.capacity}, current_load: {m.current_load})"
                for m in members
            )
            or "No team members assigned."
        )

        prompt = f"""You are an orchestration agent. Generate a detailed execution plan for this task.

Task: {task_title}
Description: {task_description}

Available Agents:
{agent_descriptions or "No agents currently online."}

Team Members:
{member_descriptions}

Available skills: generate_code, review_code, debug_code, refactor_code, explain_code, check_security, suggest_improvements, design_component

Respond ONLY with a JSON object (no markdown, no extra text) with these fields:
{{
  "summary": "Brief 1-2 sentence summary of the plan",
  "subtasks": [
    {{"title": "Step title", "skill": "skill_name", "priority": 1}}
  ],
  "selected_agent": "Name of the best agent for this task",
  "selected_agent_reason": "Why this agent is the best fit",
  "suggested_assignee": "Name or role of the person who should oversee",
  "suggested_assignee_reason": "Why this person should oversee the task",
  "alternatives_considered": [
    {{"agent": "Agent name", "reason": "Why this agent was not selected"}}
  ],
  "estimated_hours": 8
}}"""

        plan_data: dict[str, Any] = {}
        rationale = ""

        try:
            response = await litellm.acompletion(
                model=settings.default_llm_model,
                messages=[{"role": "user", "content": prompt}],
                api_key=settings.anthropic_api_key,
            )

            content = response.choices[0].message.content or "{}"

            # Strip markdown fences if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            plan_data = json.loads(content.strip())
            rationale = (
                f"Selected {plan_data.get('selected_agent', 'unknown agent')}: "
                f"{plan_data.get('selected_agent_reason', 'No reason provided.')}"
            )

        except Exception as e:
            logger.warning("LLM plan generation failed, using fallback: %s", e)
            # Fallback: build plan from available agents
            selected = agents[0] if agents else None
            others = agents[1:3] if len(agents) > 1 else []

            plan_data = {
                "summary": f"Execute '{task_title}' using available agents.",
                "subtasks": [{"title": task_title, "skill": "generate_code", "priority": 1}],
                "selected_agent": selected.name if selected else "None available",
                "selected_agent_reason": (
                    f"{selected.name} is online with skills: {', '.join(selected.skills or [])}."
                    if selected
                    else "No agents are currently online."
                ),
                "suggested_assignee": members[0].role if members else "Unassigned",
                "suggested_assignee_reason": (
                    f"Has skills: {', '.join(members[0].skills or [])}."
                    if members
                    else "No team members available."
                ),
                "alternatives_considered": [
                    {
                        "agent": a.name,
                        "reason": f"Also available with skills: {', '.join(a.skills or [])}.",
                    }
                    for a in others
                ],
                "estimated_hours": 8,
            }
            rationale = f"Fallback plan: {plan_data['selected_agent_reason']}"

        # Persist the plan
        plan_id = str(uuid4())
        plan = Plan(
            id=plan_id,
            task_id=task_id,
            project_id=project_id,
            plan_data=plan_data,
            rationale=rationale,
            status=PlanStatus.PENDING_PM_APPROVAL.value,
        )
        db.add(plan)

        return {
            "task_id": task_id,
            "plan_id": plan_id,
            "status": PlanStatus.PENDING_PM_APPROVAL.value,
            "plan_data": plan_data,
            "rationale": rationale,
        }


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
