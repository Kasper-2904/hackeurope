"""Shared context files API — list, read, and update docs/shared_context/*.md."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.auth import get_current_user
from src.services.context_service import SharedContextService
from src.storage.models import User

shared_context_router = APIRouter(prefix="/shared-context", tags=["Shared Context"])

_service = SharedContextService()


class ContextFileInfo(BaseModel):
    filename: str
    size_bytes: int
    updated_at: str


class ContextFileDetail(BaseModel):
    filename: str
    content: str
    updated_at: str


class ContextFileUpdate(BaseModel):
    content: str


def _validate_filename(filename: str) -> None:
    """Reject path traversal and non-.md filenames using path resolution."""
    if not filename.endswith(".md"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .md files are supported")
    resolved = (_service._dir / filename).resolve()
    try:
        resolved.relative_to(_service._dir.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")


@shared_context_router.get("/files", response_model=list[ContextFileInfo])
async def list_context_files(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    """List all shared context markdown files."""
    context_dir = _service._dir
    if not context_dir.exists():
        return []

    files = []
    for entry in sorted(context_dir.iterdir()):
        if entry.is_file() and entry.suffix == ".md":
            stat = entry.stat()
            files.append({
                "filename": entry.name,
                "size_bytes": stat.st_size,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
    return files


@shared_context_router.get("/files/{filename}", response_model=ContextFileDetail)
async def get_context_file(
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get the content of a shared context file."""
    _validate_filename(filename)

    path = _service._dir / filename
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    content = path.read_text(encoding="utf-8")
    stat = path.stat()
    return {
        "filename": filename,
        "content": content,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


class ContextFileCreate(BaseModel):
    filename: str
    content: str


@shared_context_router.post("/files", response_model=ContextFileDetail, status_code=status.HTTP_201_CREATED)
async def create_context_file(
    body: ContextFileCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Create a new shared context file. Filename must end in .md."""
    _validate_filename(body.filename)

    path = _service._dir / body.filename
    if path.is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File '{body.filename}' already exists. Use PUT to update it.",
        )

    _service._write_file(body.filename, body.content)

    stat = path.stat()
    return {
        "filename": body.filename,
        "content": body.content,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


@shared_context_router.put("/files/{filename}", response_model=ContextFileDetail)
async def update_context_file(
    filename: str,
    body: ContextFileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Update the content of a shared context file."""
    _validate_filename(filename)

    path = _service._dir / filename
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    _service._write_file(filename, body.content)

    stat = path.stat()
    return {
        "filename": filename,
        "content": body.content,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }
