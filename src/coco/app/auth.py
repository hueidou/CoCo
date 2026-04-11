# -*- coding: utf-8 -*-
"""Authentication module: password hashing, JWT tokens, and FastAPI middleware.

Login is disabled by default and only enabled when the environment
variable ``COCO_AUTH_ENABLED`` is set to a truthy value (``true``,
``1``, ``yes``).  Credentials are created through a web-based
registration flow rather than environment variables, so that agents
running inside the process cannot read plaintext passwords.

Supports multi-user mode with roles stored in SQLite database.

Uses bcrypt for password hashing and stdlib
for JWT tokens. The password is stored as a bcrypt hash.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

import bcrypt

from ..constant import SECRET_DIR, JWT_TOKEN_EXPIRY_SECONDS
from ..security.secret_store import (
    AUTH_SECRET_FIELDS,
    decrypt_dict_fields,
    encrypt_dict_fields,
    is_encrypted,
)

logger = logging.getLogger(__name__)

AUTH_FILE = SECRET_DIR / "auth.json"

# Paths that do NOT require authentication
_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/api/auth/login",
        "/api/auth/status",
        "/api/auth/register",
        "/api/auth/oidc/providers",
        "/api/auth/oidc/login",
        "/api/auth/oidc/callback",
        "/api/auth/oidc/status",
        "/api/version",
        "/api/settings/language",
    },
)

# Prefixes that do NOT require authentication (static assets)
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/assets/",
    "/logo.png",
    "/coco-symbol.svg",
)


# ---------------------------------------------------------------------------
# Helpers (reuse SECRET_DIR patterns from envs/store.py)
# ---------------------------------------------------------------------------


def _chmod_best_effort(path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _prepare_secret_parent(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _chmod_best_effort(path.parent, 0o700)


# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------


def _hash_password(
    password: str,
    salt: Optional[str] = None,
) -> tuple[str, str, str]:
    """Hash *password*. Returns ``(hash, "", "bcrypt")``.
    
    bcrypt handles salting internally, so the salt parameter is ignored.
    """
    # bcrypt handles salting internally
    # Cost factor 12 is a good balance between security and performance
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8"), "", "bcrypt"


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify *password* against a stored bcrypt hash.
    
    bcrypt hashes don't use external salt, the salt parameter is ignored.
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception as e:
        logger.error(f"Error verifying bcrypt password: {e}")
        return False


# ---------------------------------------------------------------------------
# Token generation / verification (HMAC-SHA256, no PyJWT needed)
# ---------------------------------------------------------------------------


def _get_jwt_secret() -> str:
    """Return the signing secret, creating one if absent."""
    data = _load_auth_data()
    secret = data.get("jwt_secret", "")
    if not secret:
        secret = secrets.token_hex(32)
        data["jwt_secret"] = secret
        _save_auth_data(data)
    return secret


def create_token(username: str, user_id: Optional[int] = None, role: Optional[str] = None) -> str:
    """
    Create an HMAC-signed token: ``base64(payload).signature``.
    
    Args:
        username: User's username
        user_id: User ID
        role: User role
    
    Returns:
        JWT token string
    """
    import base64

    secret = _get_jwt_secret()
    
    # Token expiry (always multi-user mode)
    expiry = int(time.time()) + JWT_TOKEN_EXPIRY_SECONDS
    
    # Build payload with user information
    payload_data = {
        "sub": username,
        "exp": expiry,
        "iat": int(time.time()),
    }
    
    # Add user ID and role fields
    if user_id is not None:
        payload_data["uid"] = user_id
    if role:
        payload_data["role"] = role
    
    payload = json.dumps(payload_data)
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(
        secret.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token: str, return_dict: bool = False) -> Optional[Any]:
    """
    Verify *token*, return user information.
    
    Args:
        token: JWT token to verify
        return_dict: If True, returns a dict with user info instead of just username
    
    Returns:
        - If return_dict=False: username (str) or None
        - If return_dict=True: dict with user info or None
    """
    import base64

    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        secret = _get_jwt_secret()
        expected_sig = hmac.new(
            secret.encode(),
            payload_b64.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        
        if return_dict:
            # Return full user information
            user_info = {
                "username": payload.get("sub"),
                "user_id": payload.get("uid"),
                "role": payload.get("role", "user"),
                "is_multi_user": True,
            }
            return user_info
        else:
            # Return just username for compatibility
            return payload.get("sub")
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        logger.debug("Token verification failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Auth data persistence (auth.json in SECRET_DIR)
# ---------------------------------------------------------------------------


def _load_auth_data() -> dict:
    """Load ``auth.json`` from ``SECRET_DIR``.

    Returns the parsed dict, or a sentinel with ``_auth_load_error``
    set to ``True`` when the file exists but cannot be read/parsed so
    that callers can fail closed instead of silently bypassing auth.

    Encrypted fields (``jwt_secret``) are transparently decrypted.
    Legacy plaintext values trigger an automatic re-encryption.
    """
    if AUTH_FILE.is_file():
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            needs_rewrite = any(
                isinstance(data.get(field), str)
                and data.get(field)
                and not is_encrypted(data[field])
                for field in AUTH_SECRET_FIELDS
            )
            data = decrypt_dict_fields(data, AUTH_SECRET_FIELDS)
            if needs_rewrite:
                try:
                    _save_auth_data(data)
                except Exception as enc_err:
                    logger.debug(
                        "Deferred plaintext→encrypted migration for"
                        " auth.json: %s",
                        enc_err,
                    )
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load auth file %s: %s", AUTH_FILE, exc)
            return {"_auth_load_error": True}
    return {}


def _save_auth_data(data: dict) -> None:
    """Save ``auth.json`` to ``SECRET_DIR`` with restrictive permissions.

    Sensitive fields (``jwt_secret``) are encrypted before writing.
    """
    _prepare_secret_parent(AUTH_FILE)
    encrypted_data = encrypt_dict_fields(data, AUTH_SECRET_FIELDS)
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(encrypted_data, f, indent=2, ensure_ascii=False)
    _chmod_best_effort(AUTH_FILE, 0o600)


# ---------------------------------------------------------------------------
# User management and authentication
# ---------------------------------------------------------------------------


def is_auth_enabled() -> bool:
    """Check whether authentication is enabled via environment variable.

    Returns ``True`` when ``COCO_AUTH_ENABLED`` is set to a truthy
    value (``true``, ``1``, ``yes``).  The presence of a registered
    user is checked separately by the middleware so that the first
    user can still reach the registration page.
    """
    env_flag = os.environ.get("COCO_AUTH_ENABLED", "").strip().lower()
    return env_flag in ("true", "1", "yes")


def has_registered_users() -> bool:
    """Return ``True`` if a user has been registered."""
    try:
        from ..db import SessionLocal, UserRepository
        
        db = SessionLocal()
        try:
            user_repo = UserRepository(db)
            count = user_repo.count_users(active_only=True)
            return count > 0
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error checking registered users: {e}")
        return False


def register_user(username: str, password: str, email: Optional[str] = None, role: str = "user") -> Optional[str]:
    """
    Register a user account.
    
    Args:
        username: User's username
        password: User's password
        email: User's email (optional)
        role: User's role (default: "user")
    
    Returns:
        JWT token on success, None if registration fails
    """
    try:
        from ..db import SessionLocal, UserRepository
        from ..constant import ALLOW_REGISTRATION
        
        if not ALLOW_REGISTRATION:
            logger.info("User registration is disabled by configuration")
            return None
        
        # Validate role
        if role not in ["admin", "user"]:
            logger.warning(f"Invalid role specified: {role}, defaulting to 'user'")
            role = "user"
        
        # Special case: first user registration should be admin
        db = SessionLocal()
        try:
            user_repo = UserRepository(db)
            user_count = user_repo.count_users(active_only=False)
            
            if user_count == 0:
                # First user becomes admin
                role = "admin"
                logger.info(f"First user '{username}' will be registered as admin")
            
            # Check if username already exists
            existing_user = user_repo.get_by_username(username)
            if existing_user:
                logger.info(f"Username '{username}' already exists")
                return None
            
            # Check if email already exists (if provided)
            if email:
                existing_email = user_repo.get_by_email(email)
                if existing_email:
                    logger.info(f"Email '{email}' already registered")
                    return None
            
            # Create user
            pw_hash, salt, algorithm = _hash_password(password)
            user = user_repo.create_user(
                username=username,
                role=role,
                email=email,
                password_hash=pw_hash,
                password_salt=salt,
                is_verified=(email is not None),  # TODO: implement email verification
            )
            
            logger.info(f"User '{username}' registered with role '{role}' (multi-user mode)")
            return create_token(
                username=user.username,
                user_id=user.id,
                role=user.role,
            )
            
        finally:
            db.close()
            
    except ImportError as e:
        logger.error(f"Failed to import database module: {e}")
        return None
    except Exception as e:
        logger.error(f"Registration failed: {e}", exc_info=True)
        return None


def auto_register_from_env() -> None:
    """Auto-register admin user from environment variables.

    Called once during application startup.  If ``COCO_AUTH_ENABLED``
    is truthy and both ``COCO_AUTH_USERNAME`` and ``COCO_AUTH_PASSWORD``
    are set, the admin account is created automatically — useful for
    Docker, Kubernetes, server-panel, and other automated deployments
    where interactive web registration is not practical.

    Skips silently when:
    - authentication is not enabled
    - a user has already been registered
    - either env var is missing or empty
    """
    if not is_auth_enabled():
        return
    if has_registered_users():
        return

    username = os.environ.get("COCO_AUTH_USERNAME", "").strip()
    password = os.environ.get("COCO_AUTH_PASSWORD", "").strip()
    if not username or not password:
        return

    token = register_user(username, password)
    if token:
        logger.info(
            "Auto-registered user '%s' from environment variables",
            username,
        )


def update_credentials(
    current_password: str,
    new_username: Optional[str] = None,
    new_password: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Optional[str]:
    """
    Update the registered user's username and/or password.
    
    Requires the current password for verification.  Returns a new
    token on success (because the username may have changed), or
    ``None`` if verification fails.
    """
    if user_id is None:
        logger.error("User ID is required")
        return None
    
    try:
        from ..db import SessionLocal, UserRepository
        
        db = SessionLocal()
        try:
            user_repo = UserRepository(db)
            user = user_repo.get_by_id(user_id)
            
            if not user:
                logger.error(f"User not found with ID: {user_id}")
                return None
            
            if not user.is_active:
                logger.error(f"User is inactive: {user.username}")
                return None
            
            # Verify current password
            if not verify_password(current_password, user.password_hash, user.password_salt):
                logger.debug(f"Invalid current password for user: {user.username}")
                return None
            
            # Prepare update fields
            update_fields = {}
            
            if new_username and new_username.strip():
                # Check if new username is available
                existing_user = user_repo.get_by_username(new_username.strip())
                if existing_user and existing_user.id != user_id:
                    logger.info(f"Username '{new_username}' already exists")
                    return None
                update_fields["username"] = new_username.strip()
            
            if new_password:
                # Update password
                pw_hash, salt, algorithm = _hash_password(new_password)
                update_fields["password_hash"] = pw_hash
                update_fields["password_salt"] = salt
            
            if update_fields:
                updated_user = user_repo.update_user(user_id, **update_fields)
                if not updated_user:
                    logger.error(f"Failed to update user with ID: {user_id}")
                    return None
                
                # Get the updated user
                user = user_repo.get_by_id(user_id)
            
            logger.info(f"Credentials updated for user '{user.username}' (ID: {user.id})")
            return create_token(
                username=user.username,
                user_id=user.id,
                role=user.role,
            )
            
        finally:
            db.close()
            
    except ImportError as e:
        logger.error(f"Failed to import database module: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to update credentials: {e}", exc_info=True)
        return None


def authenticate(username: str, password: str) -> Optional[str]:
    """Authenticate *username* / *password*.  Returns a token if valid."""
    try:
        from ..db import SessionLocal, UserRepository
        
        db = SessionLocal()
        try:
            user_repo = UserRepository(db)
            user = user_repo.get_by_username(username)
            
            if not user:
                logger.debug(f"User not found: {username}")
                return None
            
            if not user.is_active:
                logger.debug(f"User is inactive: {username}")
                return None
            
            # Verify password
            if user.password_hash is not None:
                if not verify_password(password, user.password_hash, user.password_salt):
                    logger.debug(f"Invalid password for user: {username}")
                    return None
            else:
                # User doesn't have a password (OIDC-only user)
                logger.debug(f"User has no password (OIDC-only): {username}")
                return None
            
            # Update last login
            user_repo.update_last_login(user.id)
            
            # Create token with extended information
            token = create_token(
                username=user.username,
                user_id=user.id,
                role=user.role,
            )
            
            logger.info(f"User authenticated: {username} (role: {user.role})")
            return token
            
        finally:
            db.close()
            
    except ImportError as e:
        logger.error(f"Failed to import database module: {e}")
        return None
    except Exception as e:
        logger.error(f"Authentication failed: {e}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that checks Bearer token on protected routes."""

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        """Check Bearer token on protected API routes; skip public paths."""
        # Even for skipped requests (localhost, etc.), parse token if present
        # so that PermissionMiddleware can use user info
        token = self._extract_token(request)
        if token:
            user_info = verify_token(token, return_dict=True)
            if user_info is not None:
                request.state.user = user_info.get("username")
                request.state.user_id = user_info.get("user_id")
                request.state.user_role = user_info.get("role", "user")
                request.state.user_info = user_info
        
        if self._should_skip_auth(request):
            return await call_next(request)

        token = self._extract_token(request)
        if not token:
            return Response(
                content=json.dumps({"detail": "Not authenticated"}),
                status_code=401,
                media_type="application/json",
            )

        # Always get full user information for multi-user mode compatibility
        user_info = verify_token(token, return_dict=True)
        if user_info is None:
            return Response(
                content=json.dumps(
                    {"detail": "Invalid or expired token"},
                ),
                status_code=401,
                media_type="application/json",
            )

        # Set user information in request state
        request.state.user = user_info.get("username")
        request.state.user_id = user_info.get("user_id")
        request.state.user_role = user_info.get("role", "user")
        request.state.user_info = user_info
        
        return await call_next(request)

    @staticmethod
    def _should_skip_auth(request: Request) -> bool:
        """Return ``True`` when the request does not require auth."""
        if not is_auth_enabled() or not has_registered_users():
            return True

        path = request.url.path

        if request.method == "OPTIONS":
            return True

        if path in _PUBLIC_PATHS or any(
            path.startswith(p) for p in _PUBLIC_PREFIXES
        ):
            return True

        # Only protect /api/ routes
        if not path.startswith("/api/"):
            return True

        # Allow localhost requests without auth (CLI runs locally)
        client_host = request.client.host if request.client else ""
        return client_host in ("127.0.0.1", "::1")

    @staticmethod
    def _extract_token(request: Request) -> Optional[str]:
        """Extract Bearer token from header or WebSocket query param."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        if "upgrade" in request.headers.get("connection", "").lower():
            return request.query_params.get("token")

        token = request.query_params.get("token")
        if token:
            return token
        return None