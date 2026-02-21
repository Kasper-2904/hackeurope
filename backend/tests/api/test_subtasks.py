"""Tests for subtask API endpoints."""

import pytest
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.subtasks import (
    create_subtask,
    get_subtask,
    list_subtasks,
    update_subtask,
    finalize_subtask,
    dispatch_subtask,
)
from src.api.schemas import SubtaskCreate, SubtaskFinalize, SubtaskUpdate
from src.core.state import SubtaskStatus, TaskStatus
from src.storage.models import AuditLog, Subtask, Task, User


async def _make_user(db: AsyncSession) -> User:
    user = User(
        id=str(uuid4()),
        username="subtask_user",
        email="subtask@test.com",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_task(db: AsyncSession, user: User) -> Task:
    task = Task(
        id=str(uuid4()),
        title="Parent Task",
        task_type="code_generation",
        status=TaskStatus.IN_PROGRESS,
        created_by_id=user.id,
    )
    db.add(task)
    await db.flush()
    return task


class TestSubtasks:
    @pytest.mark.asyncio
    async def test_create_subtask(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        task = await _make_task(db_session, user)
        await db_session.commit()

        subtask = await create_subtask(
            subtask_data=SubtaskCreate(
                task_id=task.id,
                title="Build component",
                description="Build the React component",
                priority=1,
            ),
            current_user=user,
            db=db_session,
        )

        assert subtask.title == "Build component"
        assert subtask.task_id == task.id
        assert subtask.status == SubtaskStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_list_subtasks(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        task = await _make_task(db_session, user)
        await db_session.commit()

        await create_subtask(
            subtask_data=SubtaskCreate(task_id=task.id, title="Sub 1", priority=1),
            current_user=user,
            db=db_session,
        )
        await create_subtask(
            subtask_data=SubtaskCreate(task_id=task.id, title="Sub 2", priority=2),
            current_user=user,
            db=db_session,
        )

        subtasks = await list_subtasks(current_user=user, db=db_session)

        assert len(subtasks) == 2

    @pytest.mark.asyncio
    async def test_list_subtasks_filtered_by_task(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        task1 = await _make_task(db_session, user)
        task2 = Task(
            id=str(uuid4()), title="Task 2", task_type="review", created_by_id=user.id
        )
        db_session.add(task2)
        await db_session.commit()

        await create_subtask(
            subtask_data=SubtaskCreate(task_id=task1.id, title="For task1", priority=1),
            current_user=user,
            db=db_session,
        )
        await create_subtask(
            subtask_data=SubtaskCreate(task_id=task2.id, title="For task2", priority=1),
            current_user=user,
            db=db_session,
        )

        filtered = await list_subtasks(
            current_user=user, db=db_session, task_id=task1.id
        )

        assert len(filtered) == 1
        assert filtered[0].task_id == task1.id

    @pytest.mark.asyncio
    async def test_get_subtask(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        task = await _make_task(db_session, user)
        await db_session.commit()

        created = await create_subtask(
            subtask_data=SubtaskCreate(task_id=task.id, title="Get me", priority=1),
            current_user=user,
            db=db_session,
        )

        fetched = await get_subtask(
            subtask_id=created.id, current_user=user, db=db_session
        )

        assert fetched.id == created.id
        assert fetched.title == "Get me"

    @pytest.mark.asyncio
    async def test_get_subtask_not_found(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        await db_session.commit()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_subtask(
                subtask_id="nonexistent", current_user=user, db=db_session
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_subtask(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        task = await _make_task(db_session, user)
        await db_session.commit()

        created = await create_subtask(
            subtask_data=SubtaskCreate(task_id=task.id, title="Update me", priority=1),
            current_user=user,
            db=db_session,
        )

        updated = await update_subtask(
            subtask_id=created.id,
            update_data=SubtaskUpdate(priority=5, description="Updated desc"),
            current_user=user,
            db=db_session,
        )

        assert updated.priority == 5
        assert updated.description == "Updated desc"

    @pytest.mark.asyncio
    async def test_finalize_subtask(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        task = await _make_task(db_session, user)
        await db_session.commit()

        created = await create_subtask(
            subtask_data=SubtaskCreate(task_id=task.id, title="Finalize me", priority=1),
            current_user=user,
            db=db_session,
        )

        finalized = await finalize_subtask(
            subtask_id=created.id,
            finalize_data=SubtaskFinalize(final_content={"code": "print('hello')"}),
            current_user=user,
            db=db_session,
        )

        assert finalized.status == SubtaskStatus.FINALIZED.value
        assert finalized.final_content == {"code": "print('hello')"}
        assert finalized.finalized_by_id == user.id

        # Verify audit log
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.resource_id == created.id)
        )
        audit = result.scalar_one()
        assert audit.action == "subtask_finalized"

    @pytest.mark.asyncio
    async def test_finalize_subtask_not_found(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        await db_session.commit()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await finalize_subtask(
                subtask_id="nonexistent",
                finalize_data=SubtaskFinalize(final_content={"x": 1}),
                current_user=user,
                db=db_session,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_dispatch_without_agent_400(self, db_session: AsyncSession):
        user = await _make_user(db_session)
        task = await _make_task(db_session, user)
        await db_session.commit()

        created = await create_subtask(
            subtask_data=SubtaskCreate(task_id=task.id, title="No agent", priority=1),
            current_user=user,
            db=db_session,
        )

        from fastapi import HTTPException, BackgroundTasks

        with pytest.raises(HTTPException) as exc_info:
            await dispatch_subtask(
                subtask_id=created.id,
                background_tasks=BackgroundTasks(),
                current_user=user,
                db=db_session,
            )

        assert exc_info.value.status_code == 400
        assert "assigned_agent_id" in exc_info.value.detail
