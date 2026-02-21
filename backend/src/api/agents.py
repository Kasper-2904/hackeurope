"""Agents routing endpoints."""
from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import create_agent_token, get_current_user
from src.api.schemas import (
    AgentDetail,
    AgentRegister,
    AgentResponse,
    AgentTokenResponse,
    MCPToolCall,
    MCPToolResult,
)
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import AgentStatus
from src.mcp_client.manager import get_mcp_manager
from src.services.paid_service import get_paid_service
from src.storage.database import get_db
from src.storage.models import Agent, Team, User

agents_router = APIRouter(prefix="/agents", tags=["Agents"])

@agents_router.post(
    "/register", response_model=AgentTokenResponse, status_code=status.HTTP_201_CREATED
)
async def register_agent(
    agent_data: AgentRegister,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    event_bus = get_event_bus()

    if agent_data.team_id:
        result = await db.execute(
            select(Team).where(Team.id == agent_data.team_id, Team.owner_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found or you don't have access",
            )

    agent_id = str(uuid4())
    agent = Agent(
        id=agent_id,
        name=agent_data.name,
        role=agent_data.role,
        description=agent_data.description,
        mcp_endpoint=str(agent_data.mcp_endpoint),
        owner_id=current_user.id,
        team_id=agent_data.team_id,
        status=AgentStatus.PENDING,
        extra_data=agent_data.metadata,
    )

    agent_token = create_agent_token(agent_id)
    import hashlib
    agent.api_token_hash = hashlib.sha256(agent_token.encode()).hexdigest()

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    await event_bus.publish(
        Event(
            type=EventType.AGENT_REGISTERED,
            data={
                "agent_id": agent_id,
                "name": agent_data.name,
                "role": agent_data.role,
                "mcp_endpoint": str(agent_data.mcp_endpoint),
            },
            source="api",
        )
    )

    return {
        "agent": agent,
        "token": agent_token,
        "message": "Store this token securely. It will not be shown again.",
    }


@agents_router.post("/{agent_id}/connect")
async def connect_to_agent(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    mcp_manager = get_mcp_manager()
    connection = await mcp_manager.register_agent(agent_id, agent.mcp_endpoint, connect=True)

    if connection.status != AgentStatus.ONLINE:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to agent's MCP server",
        )

    agent.status = AgentStatus.ONLINE
    agent.last_seen = datetime.utcnow()
    agent.capabilities = {
        "tools": [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in connection.capabilities.tools
        ],
        "resources": [
            {
                "uri": str(r.uri),
                "name": r.name,
                "description": r.description,
                "mime_type": r.mime_type,
            }
            for r in connection.capabilities.resources
        ],
    }

    await db.commit()

    return {
        "status": "connected",
        "agent_id": agent_id,
        "capabilities": agent.capabilities,
    }


@agents_router.get("", response_model=list[AgentResponse])
async def list_agents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    team_id: str | None = None,
) -> list[Agent]:
    query = select(Agent).where(Agent.owner_id == current_user.id)

    if team_id:
        query = query.where(Agent.team_id == team_id)

    result = await db.execute(query)
    return list(result.scalars().all())


@agents_router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent(
    agent_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Agent:
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    return agent


@agents_router.post("/{agent_id}/tools/{tool_name}", response_model=MCPToolResult)
async def call_agent_tool(
    agent_id: str,
    tool_name: str,
    tool_call: MCPToolCall,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == current_user.id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    mcp_manager = get_mcp_manager()
    tool_result = await mcp_manager.call_tool(agent_id, tool_name, tool_call.arguments)

    agent.last_seen = datetime.utcnow()
    await db.commit()

    paid_service = get_paid_service()
    customer_id = agent.team_id if agent.team_id else current_user.id
    paid_service.record_usage(
        product_id=agent_id,
        customer_id=customer_id,
        event_name="tool_call",
        data={"tool_name": tool_name, "success": tool_result.get("success", False)},
    )

    return tool_result
