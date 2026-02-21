"""Manager for multiple MCP client connections to agents."""

import asyncio
from datetime import datetime
from typing import Any

from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import AgentCapabilities, AgentStatus
from src.mcp_client.connection import AgentConnection


class MCPClientManager:
    """
    Manages connections to multiple agent MCP servers.

    This is the central hub that:
    - Maintains connections to all registered agents
    - Routes tool calls to appropriate agents
    - Handles connection lifecycle
    - Provides agent discovery by capabilities
    """

    def __init__(self):
        self._connections: dict[str, AgentConnection] = {}
        self._lock = asyncio.Lock()

    async def register_agent(
        self,
        agent_id: str,
        mcp_endpoint: str,
        connect: bool = True,
    ) -> AgentConnection:
        """
        Register a new agent and optionally connect to it.

        Args:
            agent_id: Unique identifier for the agent
            mcp_endpoint: URL of the agent's MCP server
            connect: Whether to immediately connect

        Returns:
            The AgentConnection object
        """
        async with self._lock:
            if agent_id in self._connections:
                # Agent already registered, return existing connection
                return self._connections[agent_id]

            connection = AgentConnection(
                agent_id=agent_id,
                mcp_endpoint=mcp_endpoint,
            )
            self._connections[agent_id] = connection

        if connect:
            await connection.connect()

        return connection

    async def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent and close its connection."""
        async with self._lock:
            if agent_id in self._connections:
                connection = self._connections.pop(agent_id)
                await connection.disconnect()

    async def connect_agent(self, agent_id: str) -> bool:
        """
        Connect to a registered agent's MCP server.

        Returns True if connection successful.
        """
        connection = self._connections.get(agent_id)
        if not connection:
            return False

        return await connection.connect()

    async def disconnect_agent(self, agent_id: str) -> None:
        """Disconnect from an agent's MCP server."""
        connection = self._connections.get(agent_id)
        if connection:
            await connection.disconnect()

    async def reconnect_agent(self, agent_id: str) -> bool:
        """Reconnect to an agent's MCP server."""
        connection = self._connections.get(agent_id)
        if not connection:
            return False

        await connection.disconnect()
        return await connection.connect()

    def get_connection(self, agent_id: str) -> AgentConnection | None:
        """Get a connection by agent ID."""
        return self._connections.get(agent_id)

    def get_online_agents(self) -> list[AgentConnection]:
        """Get all online agent connections."""
        return [conn for conn in self._connections.values() if conn.status == AgentStatus.ONLINE]

    def get_agents_with_tool(self, tool_name: str) -> list[AgentConnection]:
        """Find all agents that have a specific tool."""
        return [conn for conn in self.get_online_agents() if conn.has_tool(tool_name)]

    def get_agents_by_role(self, role: str) -> list[AgentConnection]:
        """
        Find agents by role.

        Note: This requires role information to be stored - typically
        fetched from the database or passed during registration.
        """
        # Role is typically stored in the database, not in the connection
        # This method would need to be enhanced to filter by role
        return self.get_online_agents()

    async def call_tool(
        self,
        agent_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call a tool on a specific agent.

        Args:
            agent_id: ID of the agent to call
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tool result
        """
        connection = self._connections.get(agent_id)
        if not connection:
            return {"success": False, "error": f"Agent {agent_id} not found"}

        if connection.status != AgentStatus.ONLINE:
            return {"success": False, "error": f"Agent {agent_id} is not online"}

        return await connection.call_tool(tool_name, arguments)

    async def call_tool_on_any(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call a tool on any agent that has it.

        Useful when you don't care which agent handles the request.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tool result
        """
        agents = self.get_agents_with_tool(tool_name)
        if not agents:
            return {"success": False, "error": f"No agent found with tool: {tool_name}"}

        # Use the first available agent
        # Could be enhanced with load balancing
        return await agents[0].call_tool(tool_name, arguments)

    async def read_resource(
        self,
        agent_id: str,
        uri: str,
    ) -> dict[str, Any]:
        """
        Read a resource from a specific agent.

        Args:
            agent_id: ID of the agent
            uri: Resource URI

        Returns:
            Resource content
        """
        connection = self._connections.get(agent_id)
        if not connection:
            return {"success": False, "error": f"Agent {agent_id} not found"}

        if connection.status != AgentStatus.ONLINE:
            return {"success": False, "error": f"Agent {agent_id} is not online"}

        return await connection.read_resource(uri)

    def get_all_tools(self) -> list[dict[str, Any]]:
        """
        Get all tools from all connected agents.

        Returns a list of tools with agent information.
        """
        tools = []
        for conn in self.get_online_agents():
            for tool in conn.capabilities.tools:
                tools.append(
                    {
                        "agent_id": conn.agent_id,
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema,
                    }
                )
        return tools

    def get_all_resources(self) -> list[dict[str, Any]]:
        """
        Get all resources from all connected agents.

        Returns a list of resources with agent information.
        """
        resources = []
        for conn in self.get_online_agents():
            for resource in conn.capabilities.resources:
                resources.append(
                    {
                        "agent_id": conn.agent_id,
                        "uri": resource.uri,
                        "name": resource.name,
                        "description": resource.description,
                        "mime_type": resource.mime_type,
                    }
                )
        return resources

    async def refresh_capabilities(self, agent_id: str) -> AgentCapabilities | None:
        """
        Refresh capabilities for a specific agent.

        Reconnects to the agent to rediscover tools and resources.
        """
        connection = self._connections.get(agent_id)
        if not connection:
            return None

        if await connection.connect():
            return connection.capabilities
        return None

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on all connections.

        Returns status summary.
        """
        online = 0
        offline = 0
        error = 0

        for conn in self._connections.values():
            if conn.status == AgentStatus.ONLINE:
                online += 1
            elif conn.status == AgentStatus.OFFLINE:
                offline += 1
            else:
                error += 1

        return {
            "total_agents": len(self._connections),
            "online": online,
            "offline": offline,
            "error": error,
            "agents": {
                agent_id: {
                    "status": conn.status.value,
                    "last_activity": conn.last_activity.isoformat() if conn.last_activity else None,
                    "tool_count": len(conn.capabilities.tools),
                    "resource_count": len(conn.capabilities.resources),
                }
                for agent_id, conn in self._connections.items()
            },
        }

    async def close_all(self) -> None:
        """Close all connections."""
        for conn in self._connections.values():
            await conn.disconnect()
        self._connections.clear()


# Global MCP client manager instance
_manager: MCPClientManager | None = None


def get_mcp_manager() -> MCPClientManager:
    """Get the global MCP client manager instance."""
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
    return _manager
