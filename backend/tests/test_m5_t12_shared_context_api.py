"""Tests for M5-T12: Shared context files API (list, get, update)."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.shared_context import (
    list_context_files,
    get_context_file,
    update_context_file,
    _service,
    _validate_filename,
    ContextFileUpdate,
)
from src.storage.models import User


# ============== Helpers ==============


def _make_mock_user() -> User:
    user = MagicMock(spec=User)
    user.id = str(uuid4())
    user.username = "testuser"
    user.is_active = True
    return user


@pytest.fixture
def context_dir(tmp_path: Path):
    """Create a temp dir with sample .md files and patch _service._dir."""
    (tmp_path / "PROJECT_OVERVIEW.md").write_text("# Project\nTest project")
    (tmp_path / "TASK_GRAPH.md").write_text("# Tasks\n- Task 1")
    (tmp_path / "TEAM_MEMBERS.md").write_text("# Team\n- Alice")
    original_dir = _service._dir
    _service._dir = tmp_path
    yield tmp_path
    _service._dir = original_dir


# ============== _validate_filename ==============


def test_validate_filename_rejects_path_traversal():
    with pytest.raises(Exception) as exc_info:
        _validate_filename("../etc/passwd")
    assert exc_info.value.status_code == 400


def test_validate_filename_rejects_traversal_with_slash():
    with pytest.raises(Exception) as exc_info:
        _validate_filename("../../etc/passwd.md")
    assert exc_info.value.status_code == 400


def test_validate_filename_rejects_non_md():
    with pytest.raises(Exception) as exc_info:
        _validate_filename("file.txt")
    assert exc_info.value.status_code == 400


def test_validate_filename_accepts_valid():
    _validate_filename("PROJECT_OVERVIEW.md")  # Should not raise


# ============== list_context_files ==============


@pytest.mark.asyncio
async def test_list_context_files(context_dir: Path):
    user = _make_mock_user()
    result = await list_context_files(current_user=user)

    assert isinstance(result, list)
    assert len(result) == 3
    filenames = [f["filename"] for f in result]
    assert "PROJECT_OVERVIEW.md" in filenames
    assert "TASK_GRAPH.md" in filenames
    assert "TEAM_MEMBERS.md" in filenames

    for f in result:
        assert "size_bytes" in f
        assert "updated_at" in f
        assert f["size_bytes"] > 0


@pytest.mark.asyncio
async def test_list_context_files_empty_dir(tmp_path: Path):
    original_dir = _service._dir
    _service._dir = tmp_path
    try:
        user = _make_mock_user()
        result = await list_context_files(current_user=user)
        assert result == []
    finally:
        _service._dir = original_dir


@pytest.mark.asyncio
async def test_list_context_files_missing_dir():
    original_dir = _service._dir
    _service._dir = Path("/nonexistent/path/that/does/not/exist")
    try:
        user = _make_mock_user()
        result = await list_context_files(current_user=user)
        assert result == []
    finally:
        _service._dir = original_dir


# ============== get_context_file ==============


@pytest.mark.asyncio
async def test_get_context_file(context_dir: Path):
    user = _make_mock_user()
    result = await get_context_file(filename="PROJECT_OVERVIEW.md", current_user=user)

    assert result["filename"] == "PROJECT_OVERVIEW.md"
    assert "# Project" in result["content"]
    assert "updated_at" in result


@pytest.mark.asyncio
async def test_get_context_file_not_found(context_dir: Path):
    user = _make_mock_user()
    with pytest.raises(Exception) as exc_info:
        await get_context_file(filename="NONEXISTENT.md", current_user=user)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_context_file_path_traversal(context_dir: Path):
    user = _make_mock_user()
    with pytest.raises(Exception) as exc_info:
        await get_context_file(filename="../secrets.md", current_user=user)
    assert exc_info.value.status_code == 400


# ============== update_context_file ==============


@pytest.mark.asyncio
async def test_update_context_file(context_dir: Path):
    user = _make_mock_user()
    body = ContextFileUpdate(content="# Updated\nNew content here")
    result = await update_context_file(
        filename="PROJECT_OVERVIEW.md", body=body, current_user=user
    )

    assert result["filename"] == "PROJECT_OVERVIEW.md"
    assert result["content"] == "# Updated\nNew content here"

    # Verify file was actually written
    actual = (context_dir / "PROJECT_OVERVIEW.md").read_text()
    assert actual == "# Updated\nNew content here"


@pytest.mark.asyncio
async def test_update_context_file_not_found(context_dir: Path):
    user = _make_mock_user()
    body = ContextFileUpdate(content="new content")
    with pytest.raises(Exception) as exc_info:
        await update_context_file(filename="NONEXISTENT.md", body=body, current_user=user)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_context_file_path_traversal(context_dir: Path):
    user = _make_mock_user()
    body = ContextFileUpdate(content="malicious")
    with pytest.raises(Exception) as exc_info:
        await update_context_file(filename="../evil.md", body=body, current_user=user)
    assert exc_info.value.status_code == 400
