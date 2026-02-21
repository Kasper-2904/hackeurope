"""Agents API endpoints - Marketplace agents with hosted inference."""

from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.api.schemas import (
    AgentChatRequest,
    AgentCreate,
    AgentDetail,
    AgentResponse,
    AgentSkillRequest,
)
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import AgentStatus
from src.services.agent_inference import get_inference_service
from src.services.paid_service import get_paid_service
from src.storage.database import get_db
from src.storage.models import Agent, User

agents_router = APIRouter(prefix="/agents", tags=["Agents"])


@agents_router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Agent:
    """Publish a new marketplace agent."""
    event_bus = get_event_bus()

    agent = Agent(
        id=str(uuid4()),
        name=agent_data.name,
        role=agent_data.role,
        description=agent_data.description,
        system_prompt=agent_data.system_prompt,
        inference_endpoint=agent_data.inference_endpoint,
        inference_api_key_encrypted=agent_data.inference_api_key,
        inference_provider=agent_data.inference_provider,
        inference_model=agent_data.inference_model,
        skills=agent_data.skills,
        owner_id=current_user.id,
        status=AgentStatus.ONLINE,
    )

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    await event_bus.publish(
        Event(
            type=EventType.AGENT_REGISTERED,
            data={
                "agent_id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "skills": agent.skills,
            },
            source="api",
        )
    )

    return agent


@agents_router.get("", response_model=list[AgentResponse])
async def list_agents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Agent]:
    """List user's agents."""
    result = await db.execute(select(Agent).where(Agent.owner_id == current_user.id))
    return list(result.scalars().all())


@agents_router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Agent:
    """Get agent details."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    return agent


@agents_router.post("/{agent_id}/chat")
async def chat_with_agent(
    agent_id: str,
    request: AgentChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Chat with an agent (for humans)."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    agent.last_seen = datetime.utcnow()
    await db.commit()

    inference_service = get_inference_service()

    # Use override or default system prompt
    system_prompt = request.system_prompt_override or agent.system_prompt

    response = await inference_service.chat(
        agent=agent,
        message=request.message,
        conversation_history=request.conversation_history,
        system_prompt=system_prompt,
    )

    paid_service = get_paid_service()
    paid_service.record_usage(
        product_id=agent_id,
        customer_id=current_user.id,
        event_name="chat",
        data={"success": True},
    )

    return {
        "agent_id": agent_id,
        "response": response,
    }


@agents_router.post("/{agent_id}/skills/execute")
async def execute_agent_skill(
    agent_id: str,
    request: AgentSkillRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Execute a skill on an agent (for orchestrator or humans)."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Verify skill is available
    if agent.skills and request.skill not in agent.skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Skill '{request.skill}' not available. Available: {agent.skills}",
        )

    agent.last_seen = datetime.utcnow()
    await db.commit()

    inference_service = get_inference_service()

    # Use override or default system prompt
    system_prompt = request.system_prompt_override or agent.system_prompt

    result_text = await inference_service.execute_skill(
        agent=agent,
        skill=request.skill,
        inputs=request.inputs,
        system_prompt=system_prompt,
    )

    paid_service = get_paid_service()
    paid_service.record_usage(
        product_id=agent_id,
        customer_id=current_user.id,
        event_name="skill_execution",
        data={"skill": request.skill, "success": True},
    )

    return {
        "agent_id": agent_id,
        "skill": request.skill,
        "result": result_text,
    }
