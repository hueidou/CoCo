# -*- coding: utf-8 -*-
"""Database initialization and setup utilities."""

import logging
import secrets
from datetime import datetime
from sqlalchemy.orm import Session

from .session import init_db, SessionLocal, is_multi_user_enabled
from .models import User, Permission, RolePermission
from .repository import UserRepository, PermissionRepository

logger = logging.getLogger(__name__)


def create_default_admin_user(db: Session) -> User:
    """
    Create default admin user if no users exist.
    
    This function is called during application startup to ensure
    there's at least one admin user in the system.
    """
    user_repo = UserRepository(db)
    
    # Check if any admin users exist
    admin_user = db.query(User).filter(User.role == "admin", User.is_active == True).first()
    if admin_user:
        logger.info(f"Admin user already exists: {admin_user.username}")
        return admin_user
    
    # Check if any users exist at all
    user_count = user_repo.count_users(active_only=False)
    if user_count > 0:
        # No admins but other users exist - promote the first user to admin
        first_user = db.query(User).order_by(User.created_at).first()
        if first_user:
            first_user.role = "admin"
            db.commit()
            logger.info(f"Promoted user '{first_user.username}' to admin")
            return first_user
    
    # Create default admin user
    from ..constant import (
        DEFAULT_ADMIN_USERNAME,
        DEFAULT_ADMIN_EMAIL,
    )
    from ..app.auth import _hash_password
    
    # Generate a random password
    default_password = secrets.token_hex(16)
    password_hash, password_salt = _hash_password(default_password)
    
    admin_user = User(
        username=DEFAULT_ADMIN_USERNAME,
        email=DEFAULT_ADMIN_EMAIL if DEFAULT_ADMIN_EMAIL else f"{DEFAULT_ADMIN_USERNAME}@localhost",
        role="admin",
        password_hash=password_hash,
        password_salt=password_salt,
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    
    logger.info(f"Created default admin user: {DEFAULT_ADMIN_USERNAME}")
    logger.warning(f"Default admin password: {default_password} (CHANGE THIS IMMEDIATELY!)")
    
    return admin_user


def create_default_permissions(db: Session) -> None:
    """
    Create default permissions and assign them to roles.
    
    This sets up the basic permission system for the application.
    """
    permission_repo = PermissionRepository(db)
    
    # Define default permissions
    default_permissions = [
        # System permissions
        ("system.config.view", "View system configuration"),
        ("system.config.update", "Update system configuration"),
        ("system.logs.view", "View system logs"),
        ("system.metrics.view", "View system metrics"),
        
        # User management permissions
        ("users.view", "View users"),
        ("users.create", "Create users"),
        ("users.update", "Update users"),
        ("users.delete", "Delete users"),
        ("users.roles.manage", "Manage user roles"),
        
        # Agent management permissions
        ("agents.view", "View agents"),
        ("agents.create", "Create agents"),
        ("agents.update", "Update agents"),
        ("agents.delete", "Delete agents"),
        ("agents.execute", "Execute agents"),
        
        # Chat permissions
        ("chats.view", "View chats"),
        ("chats.create", "Start new chats"),
        ("chats.update", "Update chats"),
        ("chats.delete", "Delete chats"),
        ("chats.history.view", "View chat history"),
        
        # Channel permissions
        ("channels.view", "View channels"),
        ("channels.create", "Create channels"),
        ("channels.update", "Update channels"),
        ("channels.delete", "Delete channels"),
        ("channels.messages.send", "Send channel messages"),
        
        # Cron job permissions
        ("cron.view", "View cron jobs"),
        ("cron.create", "Create cron jobs"),
        ("cron.update", "Update cron jobs"),
        ("cron.delete", "Delete cron jobs"),
        ("cron.execute", "Execute cron jobs"),
        
        # Skill permissions
        ("skills.view", "View skills"),
        ("skills.create", "Create skills"),
        ("skills.update", "Update skills"),
        ("skills.delete", "Delete skills"),
        ("skills.execute", "Execute skills"),
        
        # Provider permissions
        ("providers.view", "View providers"),
        ("providers.create", "Add providers"),
        ("providers.update", "Update providers"),
        ("providers.delete", "Delete providers"),
    ]
    
    # Create permissions
    permission_map = {}
    for name, description in default_permissions:
        permission = permission_repo.get_permission_by_name(name)
        if not permission:
            permission = Permission(
                name=name,
                description=description,
                enabled=True,
                created_at=datetime.utcnow(),
            )
            db.add(permission)
            db.commit()
            db.refresh(permission)
        permission_map[name] = permission
    
    # Define role-permission mappings
    admin_permissions = [
        # All permissions for admin
    ]
    
    user_permissions = [
        # Limited permissions for regular users
        "agents.view",
        "chats.view",
        "chats.create",
        "chats.update",
        "chats.delete",
        "channels.view",
        "channels.messages.send",
        "cron.view",
        "cron.execute",
        "skills.view",
    ]
    
    # Assign admin permissions (all permissions)
    for perm_name in permission_map.keys():
        # Check if mapping already exists
        existing = db.query(RolePermission).filter(
            RolePermission.role == "admin",
            RolePermission.permission_id == permission_map[perm_name].id
        ).first()
        
        if not existing:
            role_perm = RolePermission(
                role="admin",
                permission_id=permission_map[perm_name].id,
                created_at=datetime.utcnow(),
            )
            db.add(role_perm)
    
    # Assign user permissions
    for perm_name in user_permissions:
        if perm_name in permission_map:
            # Check if mapping already exists
            existing = db.query(RolePermission).filter(
                RolePermission.role == "user",
                RolePermission.permission_id == permission_map[perm_name].id
            ).first()
            
            if not existing:
                role_perm = RolePermission(
                    role="user",
                    permission_id=permission_map[perm_name].id,
                    created_at=datetime.utcnow(),
                )
                db.add(role_perm)
    
    db.commit()


def initialize_database() -> None:
    """
    Initialize the database by creating tables and setting up default data.
    
    This function should be called during application startup.
    """
    # Multi-user mode is always enabled, proceed with database initialization
    
    try:
        # Initialize database tables
        init_db()
        logger.info("Database tables created/verified")
        
        # Set up default permissions and admin user
        db = SessionLocal()
        try:
            create_default_permissions(db)
            logger.info("Default permissions created")
            
            create_default_admin_user(db)
            logger.info("Default admin user verified")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


def migrate_single_user_to_multi_user() -> bool:
    """
    Migrate from single-user auth.json to multi-user database.
    
    This function reads the existing auth.json file and migrates
    the single user to the multi-user database.
    
    Returns:
        bool: True if migration was successful or not needed
    """
    # Multi-user mode is always enabled, proceed with migration
    
    try:
        from ..app.auth import _load_auth_data, has_registered_users
        
        # Load existing auth data
        auth_data = _load_auth_data()
        if not has_registered_users() or "_auth_load_error" in auth_data:
            logger.info("No existing single user to migrate")
            return True
        
        # Get existing user data
        old_user = auth_data.get("user")
        if not old_user:
            logger.info("No user data found in auth.json")
            return True
        
        # Check if user already exists in database
        db = SessionLocal()
        try:
            user_repo = UserRepository(db)
            existing_user = user_repo.get_by_username(old_user.get("username", ""))
            if existing_user:
                logger.info(f"User '{existing_user.username}' already exists in database")
                return True
            
            # Migrate user to database
            migrated_user = user_repo.create_user(
                username=old_user.get("username", "admin"),
                role="admin",  # Single user becomes admin
                password_hash=old_user.get("password_hash"),
                password_salt=old_user.get("password_salt"),
                is_verified=True,
            )
            
            logger.info(f"Successfully migrated user '{migrated_user.username}' from auth.json to database")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to migrate single user to multi-user: {e}", exc_info=True)
        return False