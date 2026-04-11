# -*- coding: utf-8 -*-
"""Permission and role-based access control (RBAC) module.

Provides centralized, auto-discovering permission enforcement via middleware.
All routes are protected by default rules — no decorators needed.

Default rules:
- Write operations (POST/PUT/DELETE/PATCH) → admin
- Read operations (GET) → user
- Public paths (auth endpoints, /api/version) → no auth required
- User-writable whitelist → user role can perform specific write operations
"""

import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROLE_ADMIN = "admin"
ROLE_USER = "user"

# Write methods require admin by default
_ADMIN_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# Path prefixes that bypass permission checks entirely (auth, version, etc.)
_PUBLIC_PREFIXES = (
    "/api/auth/",
    "/api/version",
)

# Exact paths that bypass permission checks
_PUBLIC_PATHS = frozenset({
    "/api/version",
})

# ---------------------------------------------------------------------------
# User-writable route whitelist
# ---------------------------------------------------------------------------
# By default, all write operations (POST/PUT/DELETE/PATCH) require admin.
# This whitelist defines the write endpoints that the "user" role may access.
# Each entry is (path_pattern, method) where path_pattern uses FastAPI
# route syntax (e.g. {chat_id} for path parameters).
#
# Skills module and agent workspace files are NOT included — admin-only.
# ---------------------------------------------------------------------------

_USER_WRITABLE_ROUTES: frozenset[tuple[str, str]] = frozenset({
    # ── Console: chat interaction ──
    ("/api/console/chat", "POST"),
    ("/api/console/chat/stop", "POST"),
    ("/api/console/upload", "POST"),
    # ── Chats: own chat CRUD ──
    ("/api/chats", "POST"),
    ("/api/chats/batch-delete", "POST"),
    ("/api/chats/{chat_id}", "PUT"),
    ("/api/chats/{chat_id}", "DELETE"),
    # ── Cron: own job management ──
    ("/api/cron/jobs", "POST"),
    ("/api/cron/jobs/{job_id}", "PUT"),
    ("/api/cron/jobs/{job_id}", "DELETE"),
    ("/api/cron/jobs/{job_id}/pause", "POST"),
    ("/api/cron/jobs/{job_id}/resume", "POST"),
    ("/api/cron/jobs/{job_id}/run", "POST"),
    # ── Messages: send to channel ──
    ("/api/messages/send", "POST"),
    # ── Config: user preferences ──
    ("/api/config/user-timezone", "PUT"),
    # ── Settings: UI preferences ──
    ("/api/settings/language", "PUT"),
    # ── Workspace: upload zip ──
    ("/api/workspace/upload", "POST"),
    # ── Agent-scoped equivalents ──
    # Same routes under /api/agents/{agentId}/...
    ("/api/agents/{agentId}/console/chat", "POST"),
    ("/api/agents/{agentId}/console/chat/stop", "POST"),
    ("/api/agents/{agentId}/console/upload", "POST"),
    ("/api/agents/{agentId}/chats", "POST"),
    ("/api/agents/{agentId}/chats/batch-delete", "POST"),
    ("/api/agents/{agentId}/chats/{chat_id}", "PUT"),
    ("/api/agents/{agentId}/chats/{chat_id}", "DELETE"),
    ("/api/agents/{agentId}/cron/jobs", "POST"),
    ("/api/agents/{agentId}/cron/jobs/{job_id}", "PUT"),
    ("/api/agents/{agentId}/cron/jobs/{job_id}", "DELETE"),
    ("/api/agents/{agentId}/cron/jobs/{job_id}/pause", "POST"),
    ("/api/agents/{agentId}/cron/jobs/{job_id}/resume", "POST"),
    ("/api/agents/{agentId}/cron/jobs/{job_id}/run", "POST"),
    ("/api/agents/{agentId}/messages/send", "POST"),
    ("/api/agents/{agentId}/config/user-timezone", "PUT"),
    ("/api/agents/{agentId}/settings/language", "PUT"),
    ("/api/agents/{agentId}/workspace/upload", "POST"),
})


# ---------------------------------------------------------------------------
# PermissionMiddleware
# ---------------------------------------------------------------------------

class PermissionMiddleware(BaseHTTPMiddleware):
    """Auto-discovering RBAC middleware.

    On first request, scans all registered FastAPI routes and assigns default
    permission rules based on HTTP method, with a whitelist for user-writable
    write endpoints. No manual configuration or decorators needed.
    """

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._rules: dict[tuple[str, str], str] = {}
        self._rules_built = False

    def _build_rules(self, app):
        """Scan registered routes and assign default permission rules."""
        rules: dict[tuple[str, str], str] = {}
        for route in app.routes:
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None)
            if not path or not methods:
                continue
            if not path.startswith("/api/"):
                continue
            if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
                continue
            if path in _PUBLIC_PATHS:
                continue

            for method in methods:
                if method in ("HEAD", "OPTIONS"):
                    continue
                # Check whitelist first: user-writable write endpoints
                if (path, method) in _USER_WRITABLE_ROUTES:
                    rules[(path, method)] = ROLE_USER
                elif method in _ADMIN_METHODS:
                    rules[(path, method)] = ROLE_ADMIN
                else:
                    rules[(path, method)] = ROLE_USER

        self._rules = rules
        self._rules_built = True
        admin_count = sum(1 for r in rules.values() if r == ROLE_ADMIN)
        user_count = sum(1 for r in rules.values() if r == ROLE_USER)
        logger.info(
            f"PermissionMiddleware: {len(rules)} rules from "
            f"{len(set(p for p, _ in rules.keys()))} routes "
            f"({admin_count} admin, {user_count} user)",
        )

    def _get_required_role(self, path: str, method: str) -> Optional[str]:
        """Get required role for a path+method.

        Returns None if no rule matches (public/unprotected).
        """
        # Exact match first
        role = self._rules.get((path, method))
        if role is not None:
            return role

        # Pattern match with {param} placeholders
        for (rule_path, rule_method), rule_role in self._rules.items():
            if rule_method != method:
                continue
            if self._route_matches(rule_path, path):
                return rule_role

        return None

    async def dispatch(self, request: Request, call_next):
        """Check permissions for the requested route."""
        if not self._rules_built:
            self._build_rules(request.app)

        path = request.url.path
        method = request.method

        # Skip non-API, OPTIONS, public paths
        if not path.startswith("/api/"):
            return await call_next(request)
        if method == "OPTIONS":
            return await call_next(request)
        if path in _PUBLIC_PATHS or any(
            path.startswith(p) for p in _PUBLIC_PREFIXES
        ):
            return await call_next(request)

        # Find required role
        required_role = self._get_required_role(path, method)
        if required_role is None:
            return await call_next(request)

        # Check authentication
        user = getattr(request.state, "user", None)
        if not user:
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
            )

        # Check role
        user_role = getattr(request.state, "user_role", "")
        if user_role == required_role:
            return await call_next(request)
        if user_role == ROLE_ADMIN and required_role == ROLE_USER:
            return await call_next(request)

        return JSONResponse(
            status_code=HTTP_403_FORBIDDEN,
            content={"detail": f"Insufficient permissions. Required role: {required_role}"},
        )

    @staticmethod
    def _route_matches(pattern: str, path: str) -> bool:
        """Check if a path matches a route pattern with {param} placeholders."""
        pattern_parts = pattern.strip("/").split("/")
        path_parts = path.strip("/").split("/")
        if len(pattern_parts) != len(path_parts):
            return False
        for pp, rp in zip(pattern_parts, path_parts):
            if pp.startswith("{") and pp.endswith("}"):
                if not rp:
                    return False
            elif pp != rp:
                return False
        return True

    # -----------------------------------------------------------------------
    # Introspection API
    # -----------------------------------------------------------------------

    def get_all_rules(self) -> list[dict]:
        """Return all permission rules for the management API."""
        return [
            {
                "route_pattern": path,
                "method": method,
                "required_role": role,
            }
            for (path, method), role in sorted(self._rules.items())
        ]
