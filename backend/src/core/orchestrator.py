"""
LangGraph-based orchestrator for delegating tasks to agents.

The orchestrator:
1. Receives tasks from the API
2. Analyzes the task and creates a plan
3. Routes tasks to appropriate agents based on their capabilities
4. Manages the execution flow
5. Aggregates results
"""

import json
import litellm
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from src.config import get_settings
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import AgentStatus, TaskStatus
from src.mcp_client.manager import MCPClientManager, get_mcp_manager


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
    tool_name: str | None
    tool_arguments: dict[str, Any]

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


# ============== Node Functions ==============


async def analyze_task(state: OrchestratorState) -> OrchestratorState:
    """
    Analyze the incoming task and determine what needs to be done.

    This node examines the task type and description to understand
    what tools and agents are needed.
    """
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

    # Use LLM to analyze the task and generate a plan
    prompt = f"""
    You are an orchestration agent. Your job is to analyze a software engineering task and break it down into tools that autonomous agents should execute.
    
    Task Type: {task_type}
    Description: {description}
    
    Available tools to choose from: 
    - generate_code, write_file, review_code, check_security, suggest_improvements, generate_tests, run_tests, generate_docs, read_file, search_code
    
    Respond ONLY with a valid JSON array of tool names in the order they should be executed.
    Example: ["read_file", "generate_code", "write_file"]
    """

    try:
        response = await litellm.acompletion(
            model=settings.default_llm_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},  # Optional hint depending on provider
            api_key=settings.anthropic_api_key or "dummy_key_for_local_testing",
        )

        # Parse the JSON response
        content = response.choices[0].message.content
        try:
            # Handle potential markdown wrapping
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()

            required_tools = json.loads(content)
            if not isinstance(required_tools, list):
                required_tools = ["read_file", "generate_code", "write_file"]  # Fallback
        except Exception as e:
            print(f"Failed to parse LLM response: {e}. Content: {content}")
            required_tools = ["read_file", "generate_code", "write_file"]  # Fallback

    except Exception as e:
        print(f"LLM call failed: {e}. Falling back to default mapping.")
        # Fallback to static mapping if LLM fails
        task_tool_mapping = {
            "code_generation": ["generate_code", "write_file"],
            "code_review": ["review_code", "check_security", "suggest_improvements"],
            "test_generation": ["generate_tests", "run_tests"],
            "documentation": ["generate_docs", "write_file"],
            "bug_fix": ["read_file", "search_code", "write_file"],
            "refactor": ["read_file", "review_code", "write_file"],
            "subtask_execution": ["read_file", "generate_code", "write_file"],
        }
        required_tools = task_tool_mapping.get(task_type, ["generate_code"])

    # Create the plan based on required tools
    plan = []
    for tool in required_tools:
        plan.append(
            {
                "step": len(plan) + 1,
                "action": "call_tool",
                "tool": str(tool),
                "status": "pending",
            }
        )

    return {
        **state,
        "plan": plan,
        "current_step": 0,
        "step_results": [],
        "status": "planning",
    }


async def select_agent(state: OrchestratorState) -> OrchestratorState:
    """
    Select the best agent for the current step.

    Looks at available agents and their capabilities to find
    the best match for the required tool.
    """
    mcp_manager = get_mcp_manager()
    event_bus = get_event_bus()

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if current_step >= len(plan):
        return {**state, "selected_agent_id": None}

    step = plan[current_step]
    required_tool = step.get("tool", "")

    team_id = state.get("team_id")

    # Find agents with the required tool
    agents = mcp_manager.get_agents_with_tool(required_tool)

    # Filter agents by team_id if provided
    if team_id and agents:
        # Assuming the mcp connection or the database can tell us the agent's team
        # For now, we simulate filtering or assume the manager handles it,
        # but realistically we should verify ownership or subscription.
        pass

    if not agents:
        # No agent has the tool - try to find any online agent
        agents = mcp_manager.get_online_agents()

    if not agents:
        await event_bus.publish(
            Event(
                type=EventType.SYSTEM_WARNING,
                data={
                    "task_id": state.get("task_id"),
                    "message": f"No agents available for tool: {required_tool}",
                },
                source="orchestrator",
            )
        )
        return {
            **state,
            "selected_agent_id": None,
            "error": f"No agents available for tool: {required_tool}",
            "status": "failed",
        }

    # Select the first available agent (could be enhanced with load balancing)
    selected = agents[0]

    await event_bus.publish(
        Event(
            type=EventType.TASK_ASSIGNED,
            data={
                "task_id": state.get("task_id"),
                "agent_id": selected.agent_id,
                "tool": required_tool,
            },
            source="orchestrator",
            target=selected.agent_id,
        )
    )

    return {
        **state,
        "selected_agent_id": selected.agent_id,
        "tool_name": required_tool,
        "status": "executing",
    }


async def execute_tool(state: OrchestratorState) -> OrchestratorState:
    """
    Execute the tool on the selected agent.
    """
    mcp_manager = get_mcp_manager()
    event_bus = get_event_bus()

    agent_id = state.get("selected_agent_id")
    tool_name = state.get("tool_name")
    input_data = state.get("input_data", {})

    if not agent_id or not tool_name:
        return {
            **state,
            "error": "No agent or tool selected",
            "status": "failed",
        }

    # Prepare tool arguments based on input data
    tool_arguments = _prepare_tool_arguments(tool_name, input_data)

    # Call the tool
    result = await mcp_manager.call_tool(agent_id, tool_name, tool_arguments)

    # Record the result
    step_results = state.get("step_results", [])
    step_results.append(
        {
            "step": state.get("current_step", 0) + 1,
            "agent_id": agent_id,
            "tool": tool_name,
            "arguments": tool_arguments,
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    # Update plan status
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    if current_step < len(plan):
        plan[current_step]["status"] = "completed" if result.get("success") else "failed"
        plan[current_step]["result"] = result

    await event_bus.publish(
        Event(
            type=EventType.TASK_PROGRESS,
            data={
                "task_id": state.get("task_id"),
                "step": current_step + 1,
                "total_steps": len(plan),
                "result": result,
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
    """
    Aggregate results from all steps into a final result.
    """
    event_bus = get_event_bus()

    step_results = state.get("step_results", [])

    # Combine all results
    final_parts = []
    for result in step_results:
        tool = result.get("tool", "unknown")
        tool_result = result.get("result", {})

        if tool_result.get("success"):
            content = tool_result.get("content", [])
            for c in content:
                if c.get("type") == "text":
                    final_parts.append(f"## {tool}\n{c.get('text', '')}")
        else:
            final_parts.append(
                f"## {tool} (failed)\nError: {tool_result.get('error', 'Unknown error')}"
            )

    final_result = "\n\n".join(final_parts) if final_parts else "No results generated."

    # Check if any step failed
    has_errors = any(not r.get("result", {}).get("success", True) for r in step_results)

    status = "completed" if not has_errors else "completed_with_errors"

    await event_bus.publish(
        Event(
            type=EventType.TASK_COMPLETED,
            data={
                "task_id": state.get("task_id"),
                "subtask_id": state.get("subtask_id"),
                "status": status,
                "step_count": len(step_results),
                "handoff_required": True,  # Indicate human developer needs to take over
            },
            source="orchestrator",
        )
    )

    return {
        **state,
        "final_result": final_result,
        "status": status,
    }


def _prepare_tool_arguments(tool_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
    """Prepare arguments for a tool based on the tool name and input data."""
    # Map common input fields to tool arguments
    if tool_name in ("read_file", "write_file", "review_file"):
        return {"file_path": input_data.get("file_path", input_data.get("path", ""))}

    if tool_name == "generate_code":
        return {
            "task_description": input_data.get("description", ""),
            "language": input_data.get("language", "python"),
        }

    if tool_name == "review_code":
        return {
            "code": input_data.get("code", ""),
            "language": input_data.get("language", "python"),
        }

    if tool_name == "search_code":
        return {
            "directory": input_data.get("directory", "."),
            "pattern": input_data.get("pattern", input_data.get("search", "")),
        }

    # Default: pass through input_data
    return input_data


# ============== Routing Functions ==============


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


# ============== Graph Builder ==============


def build_orchestrator_graph() -> StateGraph:
    """
    Build the LangGraph orchestration graph.

    The graph flow:
    1. analyze_task: Understand the task and create a plan
    2. select_agent: Choose an agent for the current step
    3. execute_tool: Run the tool on the agent
    4. Loop back to select_agent or go to aggregate
    5. aggregate_results: Combine all results

    ```
    START -> analyze_task -> select_agent -> execute_tool -> should_continue?
                                  ^                              |
                                  |______________________________|
                                                |
                                         aggregate_results -> END
    ```
    """
    # Create the graph
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("analyze_task", analyze_task)
    graph.add_node("select_agent", select_agent)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("aggregate_results", aggregate_results)

    # Add edges
    graph.set_entry_point("analyze_task")
    graph.add_edge("analyze_task", "select_agent")

    # Conditional edge after agent selection
    graph.add_conditional_edges(
        "select_agent",
        check_agent_selection,
        {
            "execute": "execute_tool",
            "aggregate": "aggregate_results",
        },
    )

    # Conditional edge after execution
    graph.add_conditional_edges(
        "execute_tool",
        should_continue,
        {
            "select_agent": "select_agent",
            "aggregate": "aggregate_results",
        },
    )

    # End after aggregation
    graph.add_edge("aggregate_results", END)

    return graph


# ============== Orchestrator Class ==============


class Orchestrator:
    """
    Main orchestrator class that manages task execution.

    Usage:
        orchestrator = Orchestrator()
        result = await orchestrator.execute_task(
            task_id="123",
            task_type="code_review",
            description="Review the auth module",
            input_data={"file_path": "src/auth.py"}
        )
    """

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
        """
        Execute a task through the orchestration pipeline.

        Args:
            task_id: Unique task identifier
            task_type: Type of task (code_generation, code_review, etc.)
            description: Task description
            input_data: Additional input data for the task

        Returns:
            Final state with results
        """
        initial_state: OrchestratorState = {
            "task_id": task_id,
            "task_type": task_type,
            "task_description": description,
            "input_data": input_data or {},
            "plan": [],
            "current_step": 0,
            "selected_agent_id": None,
            "tool_name": None,
            "tool_arguments": {},
            "step_results": [],
            "final_result": None,
            "error": None,
            "status": "pending",
            "team_id": team_id,
            "user_id": user_id,
            "subtask_id": subtask_id,
        }

        # Run the graph
        final_state = await self._compiled.ainvoke(initial_state)

        return {
            "task_id": task_id,
            "status": final_state.get("status"),
            "result": final_state.get("final_result"),
            "error": final_state.get("error"),
            "steps": final_state.get("step_results"),
            "plan": final_state.get("plan"),
        }


# Global orchestrator instance
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
