import asyncio
from typing import Any, Callable
from weakref import WeakValueDictionary


class TaskManager:
    """Manages background tasks and allows cancellation."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    def start(self, task_id: str, coro: Callable[[], Any]) -> None:
        """Start a background task."""
        # Cancel existing task if any
        self.cancel(task_id)
        self._tasks[task_id] = asyncio.create_task(coro())

    def cancel(self, task_id: str) -> bool:
        """Cancel a running task. Returns True if cancelled."""
        task = self._tasks.pop(task_id, None)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_running(self, task_id: str) -> bool:
        """Check if a task is currently running."""
        task = self._tasks.get(task_id)
        return task is not None and not task.done()

    def get_status(self, task_id: str) -> str:
        """Get task status: 'running', 'completed', or 'not_found'"""
        task = self._tasks.get(task_id)
        if task is None:
            return "not_found"
        if task.done():
            return "completed"
        return "running"


_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
