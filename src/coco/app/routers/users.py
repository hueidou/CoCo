# -*- coding: utf-8 -*-
"""User management API endpoints.

Provides CRUD operations for user management (admin only).
Includes user listing, creation, update, deletion, and role management.
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import SessionLocal, UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    """User information response (sensitive data excluded)."""
    id: int
    username: str
    email: Optional[str]
    role: str
    oidc_provider: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: str
    last_login: Optional[str]


class UserCreateRequest(BaseModel):
    """Request to create a new user."""
    username: str
    password: str
    email: Optional[str] = None
    role: str = "user"


class UserUpdateRequest(BaseModel):
    """Request to update user information."""
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserPasswordResetRequest(BaseModel):
    """Request to reset user password."""
    new_password: str


class UserListResponse(BaseModel):
    """Response containing list of users."""
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _user_to_response(user) -> UserResponse:
    """Convert User model to UserResponse."""
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        oidc_provider=user.oidc_provider,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


def _validate_role(role: str) -> bool:
    """Validate that role is either 'admin' or 'user'."""
    return role in ["admin", "user"]


def _validate_password(password: str) -> tuple[bool, Optional[str]]:
    """Validate password strength."""
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    
    # Add more password validation rules as needed
    # if not any(char.isdigit() for char in password):
    #     return False, "Password must contain at least one digit"
    
    return True, None


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=UserListResponse)
async def list_users(
    request: Request,
    skip: int = 0,
    limit: int = 50,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """List users with pagination (admin only)."""
    user_repo = UserRepository(db)
    users = user_repo.get_all_users(skip=skip, limit=limit, active_only=active_only)
    total = user_repo.count_users(active_only=active_only)
    
    return UserListResponse(
        users=[_user_to_response(user) for user in users],
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
):
    """Get user by ID (admin only)."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return _user_to_response(user)


@router.post("/", response_model=UserResponse)
async def create_user(
    request: Request,
    req: UserCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new user (admin only)."""
    # Validate input
    if not req.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")
    
    if not req.password:
        raise HTTPException(status_code=400, detail="Password is required")
    
    # Validate role
    if not _validate_role(req.role):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
    
    # Validate password
    is_valid, error_msg = _validate_password(req.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    user_repo = UserRepository(db)
    
    # Check if username already exists
    existing_user = user_repo.get_by_username(req.username)
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already exists")
    
    # Check if email already exists (if provided)
    if req.email:
        existing_email = user_repo.get_by_email(req.email)
        if existing_email:
            raise HTTPException(status_code=409, detail="Email already registered")
    
    # Hash password
    from ..auth import _hash_password
    password_hash, password_salt = _hash_password(req.password)
    
    # Create user
    user = user_repo.create_user(
        username=req.username,
        role=req.role,
        email=req.email,
        password_hash=password_hash,
        password_salt=password_salt,
    )
    
    logger.info(f"Admin created user: {req.username} (role: {req.role})")
    return _user_to_response(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: int,
    req: UserUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update user information (admin only)."""
    user_repo = UserRepository(db)
    
    # Check if user exists
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prepare update fields
    update_fields = {}
    
    if req.username is not None:
        if not req.username.strip():
            raise HTTPException(status_code=400, detail="Username cannot be empty")
        
        # Check if new username is available
        existing_user = user_repo.get_by_username(req.username)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=409, detail="Username already exists")
        
        update_fields["username"] = req.username.strip()
    
    if req.email is not None:
        if req.email.strip():
            # Check if new email is available
            existing_email = user_repo.get_by_email(req.email)
            if existing_email and existing_email.id != user_id:
                raise HTTPException(status_code=409, detail="Email already registered")
            update_fields["email"] = req.email.strip()
        else:
            update_fields["email"] = None
    
    if req.role is not None:
        if not _validate_role(req.role):
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
        update_fields["role"] = req.role
    
    if req.is_active is not None:
        update_fields["is_active"] = req.is_active
    
    # Apply updates
    if update_fields:
        user = user_repo.update_user(user_id, **update_fields)
        if not user:
            raise HTTPException(status_code=500, detail="Failed to update user")
        
        action = "updated"
        if "is_active" in update_fields and not update_fields["is_active"]:
            action = "deactivated" if not user.is_active else "reactivated"
        logger.info(f"Admin {action} user: {user.username} (ID: {user_id})")
    
    return _user_to_response(user)


@router.delete("/{user_id}")
async def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
):
    """Delete (deactivate) a user (admin only).
    
    This is a soft delete - sets is_active=False instead of removing from database.
    """
    user_repo = UserRepository(db)
    
    # Check if user exists
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Soft delete (deactivate)
    success = user_repo.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete user")
    
    logger.info(f"Admin deleted (deactivated) user: {user.username} (ID: {user_id})")
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    request: Request,
    user_id: int,
    req: UserPasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Reset user password (admin only)."""
    # Validate password
    is_valid, error_msg = _validate_password(req.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    user_repo = UserRepository(db)
    
    # Check if user exists
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Hash new password
    from ..auth import _hash_password
    password_hash, password_salt = _hash_password(req.new_password)
    
    # Update password
    user = user_repo.update_user(
        user_id,
        password_hash=password_hash,
        password_salt=password_salt,
    )
    
    if not user:
        raise HTTPException(status_code=500, detail="Failed to reset password")
    
    logger.info(f"Admin reset password for user: {user.username} (ID: {user_id})")
    return {"message": "Password reset successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get current authenticated user's information."""
    # Get current user from request state (set by AuthMiddleware)
    user_id = getattr(request.state, "user_id", None)
    username = getattr(request.state, "user", None)
    
    if not user_id and not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_repo = UserRepository(db)
    
    # Try to get user by ID first, then by username
    user = None
    if user_id:
        user = user_repo.get_by_id(user_id)
    
    if not user and username:
        user = user_repo.get_by_username(username)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return _user_to_response(user)