# -*- coding: utf-8 -*-
"""User-level data ownership utilities.

Provides helpers for enforcing per-user data isolation in API endpoints.
All ownership checks use `user_id` (string, from the auth system's JWT sub claim),
which is set by AuthMiddleware on `request.state.user`.

Isolation rules:
- admin users: no filtering, can access all resources
- non-admin users: can only access resources where user_id == their id
- unauthenticated requests: denied (auth is always required)
"""

from typing import Optional, Callable, List, TypeVar

from fastapi import HTTPException, Request
from starlette.status import HTTP_403_FORBIDDEN

T = TypeVar("T")


def get_caller_identity(request: Request) -> tuple[str, str]:
    """Extract the authenticated user's identity from request state.

    Args:
        request: FastAPI/Starlette request object

    Returns:
        (user_id, role) tuple:
        - user_id: username (str) from JWT
        - role: "admin" or "user"

    Raises:
        HTTPException: 403 if user is not authenticated
    """
    user_id = getattr(request.state, "user", None)
    role = getattr(request.state, "user_role", "")
    if not user_id or not role:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Authentication required",
        )
    return user_id, role


def filter_by_user(
    user_id: str,
    role: str,
    items: List[T],
    get_user_id: Callable[[T], Optional[str]] = lambda x: x.user_id,
) -> List[T]:
    """Filter a list of resources by user ownership.

    - admin users see everything
    - non-admin users see only their own items

    Args:
        user_id: The caller's user ID
        role: The caller's role
        items: List of resources to filter
        get_user_id: Function to extract user_id from a resource

    Returns:
        Filtered list of resources
    """
    # Admin sees everything
    if role == "admin":
        return items

    # Non-admin: only own items
    return [
        item for item in items
        if get_user_id(item) == user_id
    ]


def check_user_access(
    user_id: str,
    role: str,
    resource_user_id: Optional[str],
) -> bool:
    """Check if a user has access to a specific resource.

    Args:
        user_id: The caller's user ID
        role: The caller's role
        resource_user_id: The resource's user_id

    Returns:
        True if access is allowed, False otherwise
    """
    # Admin always has access
    if role == "admin":
        return True

    # Owner has access
    if resource_user_id == user_id:
        return True

    return False


def require_user_access(
    user_id: str,
    role: str,
    resource_user_id: Optional[str],
    detail: str = "You do not have permission to access this resource",
) -> None:
    """Check user access and raise 403 if denied.

    Args:
        user_id: The caller's user ID
        role: The caller's role
        resource_user_id: The resource's user_id
        detail: Error message on denial

    Raises:
        HTTPException: 403 if access is denied
    """
    if not check_user_access(user_id, role, resource_user_id):
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail=detail)
