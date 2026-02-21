"""In-memory async event bus for agent communication."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine
from uuid import uuid4

from src.config import get_settings


class EventType(str, Enum):
    """Types of events in the system."""

    # Agent lifecycle
    AGENT_REGISTERED = "agent.registered"
    AGENT_CONNECTED = "agent.connected"
    AGENT_DISCONNECTED = "agent.disconnected"
    AGENT_CAPABILITIES_UPDATED = "agent.capabilities_updated"

    # Task lifecycle
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # MCP events
    MCP_TOOL_CALLED = "mcp.tool_called"
    MCP_TOOL_RESULT = "mcp.tool_result"
    MCP_RESOURCE_READ = "mcp.resource_read"

    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


@dataclass
class Event:
    """Represents an event in the system."""

    type: EventType
    data: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str | None = None  # Agent ID or "orchestrator"
    target: str | None = None  # Target agent ID if specific


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async in-memory event bus using asyncio.

    Supports:
    - Topic-based pub/sub
    - Wildcard subscriptions (e.g., "agent.*")
    - Async event handlers
    """

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue(
            maxsize=get_settings().event_bus_max_queue_size
        )
        self._running = False
        self._processor_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the event processor."""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        """Stop the event processor."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None

    def subscribe(self, event_type: EventType | str, handler: EventHandler) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: The event type to subscribe to. Can use wildcards like "agent.*"
            handler: Async function to call when event is received
        """
        topic = event_type.value if isinstance(event_type, EventType) else event_type
        self._handlers[topic].append(handler)

    def unsubscribe(self, event_type: EventType | str, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type."""
        topic = event_type.value if isinstance(event_type, EventType) else event_type
        if handler in self._handlers[topic]:
            self._handlers[topic].remove(handler)

    async def publish(self, event: Event) -> None:
        """
        Publish an event to the bus.

        Args:
            event: The event to publish
        """
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event if queue is full
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass

    async def _process_events(self) -> None:
        """Process events from the queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing event: {e}")

    async def _dispatch(self, event: Event) -> None:
        """Dispatch an event to all matching handlers."""
        topic = event.type.value

        # Get exact match handlers
        handlers = list(self._handlers.get(topic, []))

        # Get wildcard handlers (e.g., "agent.*" matches "agent.connected")
        prefix = topic.rsplit(".", 1)[0] if "." in topic else topic
        wildcard_handlers = self._handlers.get(f"{prefix}.*", [])
        handlers.extend(wildcard_handlers)

        # Get global wildcard handlers
        handlers.extend(self._handlers.get("*", []))

        # Execute all handlers concurrently
        if handlers:
            await asyncio.gather(
                *[self._safe_call(handler, event) for handler in handlers],
                return_exceptions=True,
            )

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """Safely call a handler, catching any exceptions."""
        try:
            await handler(event)
        except Exception as e:
            print(f"Error in event handler for {event.type}: {e}")


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
