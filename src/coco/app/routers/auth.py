# -*- coding: utf-8 -*-
"""Authentication API endpoints.

User management is handled by Keycloak (OIDC). Local login/register/profile
endpoints are disabled — all authentication goes through OIDC.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..auth import (
    has_registered_users,
    is_auth_enabled,
    verify_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatusResponse(BaseModel):
    enabled: bool
    has_users: bool
    allow_registration: bool
    oidc_only: bool = True


class LoginResponse(BaseModel):
    token: str
    username: str
    user_id: Optional[int] = None
    role: str = "user"


@router.post("/login")
async def login():
    """Local login is disabled. Use OIDC (Keycloak) instead."""
    raise HTTPException(
        status_code=410,
        detail="Local login is disabled. Please use OIDC (Keycloak) to sign in.",
    )


@router.post("/register")
async def register():
    """Local registration is disabled. Use OIDC (Keycloak) instead."""
    raise HTTPException(
        status_code=410,
        detail="Local registration is disabled. Please use OIDC (Keycloak) to sign in.",
    )


@router.get("/status")
async def auth_status():
    """Check if authentication is enabled and whether a user exists."""
    return AuthStatusResponse(
        enabled=is_auth_enabled(),
        has_users=has_registered_users(),
        allow_registration=False,
        oidc_only=True,
    )


@router.get("/verify")
async def verify(request: Request):
    """Verify that the caller's Bearer token is still valid."""
    if not is_auth_enabled():
        return {"valid": True, "username": "", "role": "user"}

    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")

    user_info = verify_token(token, return_dict=True)
    if user_info is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    return {
        "valid": True,
        "username": user_info.get("username"),
        "role": user_info.get("role", "user"),
        "user_id": user_info.get("user_id"),
    }


class UpdateProfileRequest(BaseModel):
    current_password: str
    new_username: str | None = None
    new_password: str | None = None
    email: str | None = None


@router.post("/update-profile")
async def update_profile():
    """Profile updates are managed by Keycloak. Use Keycloak's account console."""
    raise HTTPException(
        status_code=410,
        detail="Profile management is handled by Keycloak. "
               "Please use the Keycloak account console to update your profile.",
    )
