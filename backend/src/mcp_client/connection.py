"""MCP connection management for connecting to agent MCP servers."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    ListResourcesResult,
    ReadResourceResult,
    Tool,
    Resource,
)

from src.config import get_settings
from src.core.event_bus import Event, EventType, get_event_bus
from src.core.state import AgentCapabilities, AgentStatus, MCPResource, MCPTool


@dataclass
class AgentConnection:
    """
    Represents a connection to an agent's MCP server.

    The platform acts as an MCP Client connecting to each agent's MCP Server.
    """

    agent_id: str
    mcp_endpoint: str
    status: AgentStatus = AgentStatus.PENDING

    # MCP session
    _session: ClientSession | None = None
    _http_client: httpx.AsyncClient | None = None

    # Cached capabilities
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)

    # Connection metadata
    connected_at: datetime | None = None
    last_activity: datetime | None = None

    async def connect(self) -> bool:
        """
        Connect to the agent's MCP server and discover capabilities.

        Returns True if connection successful.
        """
        settings = get_settings()
        event_bus = get_event_bus()

        try:
            # Create HTTP client for Streamable HTTP transport
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.mcp_connection_timeout)
            )

            # Connect using Streamable HTTP transport
            async with streamablehttp_client(self.mcp_endpoint) as (read, write, _):
                async with ClientSession(read, write) as session:
                    self._session = session

                    # Initialize the MCP connection
                    await session.initialize()

                    # Discover capabilities
                    await self._discover_capabilities()

                    self.status = AgentStatus.ONLINE
                    self.connected_at = datetime.utcnow()
                    self.last_activity = datetime.utcnow()

                    # Publish connection event
                    await event_bus.publish(
                        Event(
                            type=EventType.AGENT_CONNECTED,
                            data={
                                "agent_id": self.agent_id,
                                "capabilities": {
                                    "tools": [t.name for t in self.capabilities.tools],
                                    "resources": [r.uri for r in self.capabilities.resources],
                                },
                            },
                            source="mcp_client",
                        )
                    )

                    return True

        except Exception as e:
            self.status = AgentStatus.ERROR
            await event_bus.publish(
                Event(
                    type=EventType.SYSTEM_ERROR,
                    data={
                        "agent_id": self.agent_id,
                        "error": str(e),
                        "context": "mcp_connection",
                    },
                    source="mcp_client",
                )
            )
            return False

    async def disconnect(self) -> None:
        """Disconnect from the agent's MCP server."""
        event_bus = get_event_bus()

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self._session = None
        self.status = AgentStatus.OFFLINE

        await event_bus.publish(
            Event(
                type=EventType.AGENT_DISCONNECTED,
                data={"agent_id": self.agent_id},
                source="mcp_client",
            )
        )

    async def _discover_capabilities(self) -> None:
        """Discover tools and resources from the connected MCP server."""
        if not self._session:
            return

        # List tools
        try:
            tools_result: ListToolsResult = await self._session.list_tools()
            self.capabilities.tools = [
                MCPTool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else None,
                )
                for tool in tools_result.tools
            ]
        except Exception:
            self.capabilities.tools = []

        # List resources
        try:
            resources_result: ListResourcesResult = await self._session.list_resources()
            self.capabilities.resources = [
                MCPResource(
                    uri=resource.uri,
                    name=resource.name,
                    description=resource.description,
                    mime_type=resource.mimeType if hasattr(resource, "mimeType") else None,
                )
                for resource in resources_result.resources
            ]
        except Exception:
            self.capabilities.resources = []

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call a tool on the agent's MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool result as a dictionary
        """
        if not self._session:
            raise RuntimeError(f"Not connected to agent {self.agent_id}")

        event_bus = get_event_bus()

        # Publish tool call event
        await event_bus.publish(
            Event(
                type=EventType.MCP_TOOL_CALLED,
                data={
                    "agent_id": self.agent_id,
                    "tool_name": tool_name,
                    "arguments": arguments or {},
                },
                source="orchestrator",
                target=self.agent_id,
            )
        )

        try:
            result: CallToolResult = await self._session.call_tool(
                tool_name,
                arguments or {},
            )

            self.last_activity = datetime.utcnow()

            # Extract content from result
            response = {
                "success": not result.isError if hasattr(result, "isError") else True,
                "content": [],
            }

            for content in result.content:
                if hasattr(content, "text"):
                    response["content"].append({"type": "text", "text": content.text})
                elif hasattr(content, "data"):
                    response["content"].append({"type": "data", "data": content.data})

            # Publish tool result event
            await event_bus.publish(
                Event(
                    type=EventType.MCP_TOOL_RESULT,
                    data={
                        "agent_id": self.agent_id,
                        "tool_name": tool_name,
                        "result": response,
                    },
                    source=self.agent_id,
                )
            )

            return response

        except Exception as e:
            error_response = {"success": False, "error": str(e)}

            await event_bus.publish(
                Event(
                    type=EventType.MCP_TOOL_RESULT,
                    data={
                        "agent_id": self.agent_id,
                        "tool_name": tool_name,
                        "result": error_response,
                    },
                    source=self.agent_id,
                )
            )

            return error_response

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """
        Read a resource from the agent's MCP server.

        Args:
            uri: URI of the resource to read

        Returns:
            Resource content as a dictionary
        """
        if not self._session:
            raise RuntimeError(f"Not connected to agent {self.agent_id}")

        event_bus = get_event_bus()

        try:
            result: ReadResourceResult = await self._session.read_resource(uri)

            self.last_activity = datetime.utcnow()

            # Extract content
            contents = []
            for content in result.contents:
                if hasattr(content, "text"):
                    contents.append(
                        {
                            "uri": content.uri,
                            "text": content.text,
                            "mimeType": getattr(content, "mimeType", None),
                        }
                    )

            response = {"success": True, "contents": contents}

            await event_bus.publish(
                Event(
                    type=EventType.MCP_RESOURCE_READ,
                    data={
                        "agent_id": self.agent_id,
                        "uri": uri,
                        "content_count": len(contents),
                    },
                    source=self.agent_id,
                )
            )

            return response

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_tool(self, tool_name: str) -> MCPTool | None:
        """Get a tool by name from cached capabilities."""
        for tool in self.capabilities.tools:
            if tool.name == tool_name:
                return tool
        return None

    def has_tool(self, tool_name: str) -> bool:
        """Check if agent has a specific tool."""
        return self.get_tool(tool_name) is not None
