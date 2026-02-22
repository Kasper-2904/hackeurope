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
from src.storage.models import Agent, Plan, TeamMember


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


async def analyze_task(state: OrchestratorState) -> OrchestratorState:
    """Analyze the task and create a plan using LLM."""
    event_bus = get_event_bus()

    task_type = state.get("task_type", "")
    description = state.get("task_description", "")

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

    prompt = f"""
    You are an orchestration agent. Analyze this task and break it down into skills to execute.
    
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
    }


async def select_agent(state: OrchestratorState) -> OrchestratorState:
    """Select the best agent for the current step based on skills."""
    event_bus = get_event_bus()

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    selection_log = list(state.get("agent_selection_log", []))

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
            reason = f"Agent '{selected.name}' has the required skill '{required_skill}'."
        elif agents:
            selected = agents[0]
            reason = f"No agent matched skill '{required_skill}'; falling back to '{selected.name}'."
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
            "agent_selection_log": selection_log,
            "error": f"No agents available for skill: {required_skill}",
            "status": "failed",
        }

    await event_bus.publish(
        Event(
            type=EventType.TASK_ASSIGNED,
            data={
                "task_id": state.get("task_id"),
                "agent_id": selected.id,
                "agent_name": selected.name,
                "skill": required_skill,
                "reason": reason,
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

        # Prepare skill inputs
        skill_inputs = _prepare_skill_inputs(skill_name, input_data)

        # Execute skill via inference service
        result_text = await inference_service.execute_skill(
            agent=agent,
            skill=skill_name,
            inputs=skill_inputs,
            system_prompt=agent.system_prompt,
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
    if skill_name == "generate_code":
        return {
            "task": input_data.get("description", ""),
            "language": input_data.get("language", "python"),
        }

    if skill_name == "review_code":
        return {
            "code": input_data.get("code", ""),
        }

    if skill_name == "debug_code":
        return {
            "code": input_data.get("code", ""),
            "error": input_data.get("error", ""),
        }

    if skill_name == "refactor_code":
        return {
            "code": input_data.get("code", ""),
            "instructions": input_data.get("instructions", ""),
        }

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
            "agent_selection_log": [],
            "final_result": None,
            "error": None,
            "status": "pending",
            "team_id": team_id,
            "user_id": user_id,
            "subtask_id": subtask_id,
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
        result = await db.execute(
            select(Agent).where(Agent.status == AgentStatus.ONLINE)
        )
        agents = list(result.scalars().all())

        agent_descriptions = "\n".join(
            f"- {a.name} (role: {a.role}, skills: {', '.join(a.skills or [])}): {a.description or 'No description'}"
            for a in agents
        )

        # Query team members for assignee suggestions
        tm_result = await db.execute(
            select(TeamMember).where(TeamMember.project_id == project_id)
        )
        members = list(tm_result.scalars().all())

        member_descriptions = "\n".join(
            f"- Member {m.user_id[:8]} (role: {m.role}, skills: {', '.join(m.skills or [])}, capacity: {m.capacity}, current_load: {m.current_load})"
            for m in members
        ) or "No team members assigned."

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
                    if selected else "No agents are currently online."
                ),
                "suggested_assignee": members[0].role if members else "Unassigned",
                "suggested_assignee_reason": (
                    f"Has skills: {', '.join(members[0].skills or [])}."
                    if members else "No team members available."
                ),
                "alternatives_considered": [
                    {"agent": a.name, "reason": f"Also available with skills: {', '.join(a.skills or [])}."}
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
