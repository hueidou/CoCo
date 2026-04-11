# -*- coding: utf-8 -*-
"""SQLAlchemy ORM models for multi-user support."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255))
    password_salt = Column(String(255))
    role = Column(String(20), default="user")  # "admin" or "user"
    email = Column(String(255))
    
    # OIDC fields
    oidc_id = Column(String(255))  # OIDC provider user ID
    oidc_provider = Column(String(100))  # e.g., "keycloak", "google", "github"
    oidc_email = Column(String(255))
    
    # User status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"

    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.role == "admin"

    def to_dict(self):
        """Convert user to dictionary, excluding sensitive fields."""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "email": self.email,
            "oidc_provider": self.oidc_provider,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class UserSession(Base):
    """User sessions for tracking active sessions."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    session_token = Column(String(255), unique=True, nullable=False)
    user_agent = Column(Text)
    ip_address = Column(String(45))
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)


class Permission(Base):
    """Permission model for fine-grained access control."""
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RolePermission(Base):
    """Mapping between roles and permissions."""
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True)
    role = Column(String(20), nullable=False)  # "admin" or "user"
    permission_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserChannelOverride(Base):
    """Per-user channel config overrides (non-agent-level fields only)."""
    __tablename__ = "user_channel_overrides"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False)  # JWT sub (username)
    agent_id = Column(String(100), nullable=False, default="default")
    channel_key = Column(String(100), nullable=False)  # e.g. "dingtalk", "telegram"
    overrides = Column(Text, nullable=False)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<UserChannelOverride(user_id='{self.user_id}', "
            f"agent_id='{self.agent_id}', channel_key='{self.channel_key}')>"
        )


class AuditLog(Base):
    """Audit log for tracking important system events."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)  # Null for system events
    username = Column(String(100), nullable=True)
    
    # Event details
    event_type = Column(String(50), nullable=False)  # "login", "register", "password_change", "user_update", "system_event"
    event_action = Column(String(100), nullable=False)  # e.g., "successful_login", "failed_login", "user_created"
    event_description = Column(Text, nullable=True)
    
    # Context information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Metadata
    success = Column(Boolean, default=True)
    additional_data = Column(Text, nullable=True)  # JSON data for any extra context
    
    created_at = Column(DateTime, default=datetime.utcnow)