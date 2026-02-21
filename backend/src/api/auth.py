"""Authentication utilities using JWT."""

from datetime import datetime, timedelta
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.core.state import UserRole
from src.storage.database import get_db
from src.storage.models import TeamMember, User

# Bearer token scheme
bearer_scheme = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def create_agent_token(agent_id: str) -> str:
    """Create a long-lived token for an agent."""
    settings = get_settings()
    # Agent tokens have longer expiry
    expire = datetime.utcnow() + timedelta(days=365)
    to_encode = {
        "sub": agent_id,
        "type": "agent",
        "exp": expire,
    }
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get the current authenticated user from JWT token."""
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if user_id is None:
            raise credentials_exception

        # Don't allow agent tokens for user endpoints
        if token_type == "agent":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent tokens cannot access user endpoints",
            )

    except JWTError as e:
        raise credentials_exception from e


async def check_user_role_for_project(
    db: AsyncSession,
    user_id: str,
    project_id: str,
    required_roles: list[UserRole],
) -> bool:
    """
    Check if a user has one of the required roles for a project.

    Args:
        db: Database session
        user_id: User ID to check
        project_id: Project ID to check role for
        required_roles: List of acceptable roles

    Returns:
        True if user has one of the required roles, False otherwise
    """
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.user_id == user_id,
            TeamMember.project_id == project_id,
        )
    )
    team_member = result.scalar_one_or_none()

    if not team_member:
        return False

    return team_member.role in [r.value for r in required_roles]


async def require_pm_role_for_project(
    db: AsyncSession,
    user: User,
    project_id: str,
) -> None:
    """
    Verify that the user has PM or ADMIN role for the given project.

    Raises HTTPException 403 if user doesn't have the required role.
    Superusers are always allowed.

    Args:
        db: Database session
        user: Current user
        project_id: Project ID to check role for

    Raises:
        HTTPException: 403 if user doesn't have PM/ADMIN role
    """
    # Superusers bypass role checks
    if user.is_superuser:
        return

    has_role = await check_user_role_for_project(
        db, user.id, project_id, [UserRole.PM, UserRole.ADMIN]
    )

    if not has_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only PM or Admin can perform this action",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def verify_agent_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict:
    """Verify an agent's JWT token and return the payload."""
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid agent credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        agent_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if agent_id is None or token_type != "agent":
            raise credentials_exception

        return {"agent_id": agent_id}

    except JWTError:
        raise credentials_exception
