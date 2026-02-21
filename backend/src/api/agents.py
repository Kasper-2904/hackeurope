"""Agents API endpoints - Marketplace agents with hosted inference."""

import logging
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
from src.core.state import AgentStatus, PricingType, SubscriptionStatus
from src.services.agent_inference import get_inference_service
from src.services.paid_service import get_paid_service
from src.storage.database import get_db
from src.storage.models import Agent, AgentSubscription, MarketplaceAgent, Team, User

logger = logging.getLogger(__name__)


async def verify_agent_subscription(
    db: AsyncSession,
    agent_id: str,
    team_id: str,
    user_id: str,
) -> None:
    """
    Verify that a team has access to use an agent.

    Access is granted if:
    1. User owns the agent directly, OR
    2. Team owns the agent, OR
    3. Agent is FREE in marketplace, OR
    4. Team has active subscription to PAID marketplace agent

    Raises HTTPException 403 if no access.
    """
    # Check if user owns the agent
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.owner_id == user_id))
    if result.scalar_one_or_none():
        return  # Owner always has access

    # Check if team owns the agent
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.team_id == team_id))
    if result.scalar_one_or_none():
        return  # Team's own agent

    # Check if it's a marketplace agent
    result = await db.execute(select(MarketplaceAgent).where(MarketplaceAgent.agent_id == agent_id))
    marketplace_agent = result.scalar_one_or_none()

    if not marketplace_agent:
        # Not a marketplace agent and user doesn't own it
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this agent",
        )

    # FREE marketplace agents - no subscription needed
    if marketplace_agent.pricing_type == PricingType.FREE.value:
        return

    # PAID agents - require active subscription
    result = await db.execute(
        select(AgentSubscription).where(
            AgentSubscription.team_id == team_id,
            AgentSubscription.marketplace_agent_id == marketplace_agent.id,
            AgentSubscription.status == SubscriptionStatus.ACTIVE.value,
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team does not have an active subscription to this agent. Please subscribe first.",
        )


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
    """Chat with an agent (for humans). Requires active subscription for marketplace agents."""
    # Verify team exists and user has access
    result = await db.execute(
        select(Team).where(Team.id == request.team_id, Team.owner_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Check subscription access
    await verify_agent_subscription(db, agent_id, request.team_id, current_user.id)

    # Check usage limit before doing work
    paid_service = get_paid_service()
    effective_team_id = agent.team_id or f"user_{current_user.id}"
    if not await paid_service.check_usage_limit(effective_team_id, db):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily usage limit exceeded",
        )

    agent.last_seen = datetime.utcnow()

    inference_service = get_inference_service()

    # Use override or default system prompt
    system_prompt = request.system_prompt_override or agent.system_prompt

    response = await inference_service.chat(
        agent=agent,
        message=request.message,
        conversation_history=request.conversation_history,
        system_prompt=system_prompt,
    )

    # Track usage
    try:
        await paid_service.track_usage(
            db=db,
            team_id=effective_team_id,
            user_id=current_user.id,
            usage_type="chat",
            data={"agent_id": agent_id, "team_id": request.team_id},
        )
    except Exception as e:
        logger.warning("Usage tracking failed in chat: %s", e)

    await db.commit()

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
    """Execute a skill on an agent. Requires active subscription for marketplace agents."""
    # Verify team exists and user has access
    result = await db.execute(
        select(Team).where(Team.id == request.team_id, Team.owner_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    await verify_agent_subscription(db, agent_id, request.team_id, current_user.id)

    # Check usage limit
    paid_service = get_paid_service()
    effective_team_id = agent.team_id or f"user_{current_user.id}"
    if not await paid_service.check_usage_limit(effective_team_id, db):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily usage limit exceeded",
        )

    # Verify skill is available
    if agent.skills and request.skill not in agent.skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Skill '{request.skill}' not available. Available: {agent.skills}",
        )

    agent.last_seen = datetime.utcnow()

    inference_service = get_inference_service()

    # Use override or default system prompt
    system_prompt = request.system_prompt_override or agent.system_prompt

    result_text = await inference_service.execute_skill(
        agent=agent,
        skill=request.skill,
        inputs=request.inputs,
        system_prompt=system_prompt,
    )

    # Track usage
    try:
        await paid_service.track_usage(
            db=db,
            team_id=effective_team_id,
            user_id=current_user.id,
            usage_type="skill_execution",
            data={"agent_id": agent_id, "team_id": request.team_id, "skill": request.skill},
        )
    except Exception as e:
        logger.warning("Usage tracking failed in skill execution: %s", e)

    await db.commit()

    return {
        "agent_id": agent_id,
        "skill": request.skill,
        "result": result_text,
    }
