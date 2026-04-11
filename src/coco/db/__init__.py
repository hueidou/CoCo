# -*- coding: utf-8 -*-
"""Database module for multi-user support."""

from .session import (
    engine, 
    SessionLocal, 
    get_db, 
    init_db, 
    is_multi_user_enabled,
    get_database_path,
    database_exists,
)
from .models import Base, User, UserSession, Permission, RolePermission, UserChannelOverride
from .repository import UserRepository, SessionRepository, PermissionRepository
from .user_channel_repo import UserChannelRepo
from .initializer import (
    create_default_admin_user,
    create_default_permissions,
    initialize_database,
    migrate_single_user_to_multi_user,
)

__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "is_multi_user_enabled",
    "get_database_path",
    "database_exists",
    "Base",
    "User",
    "UserSession",
    "Permission",
    "RolePermission",
    "UserChannelOverride",
    "UserRepository",
    "SessionRepository",
    "PermissionRepository",
    "UserChannelRepo",
    "create_default_admin_user",
    "create_default_permissions",
    "initialize_database",
    "migrate_single_user_to_multi_user",
]