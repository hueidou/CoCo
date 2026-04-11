# -*- coding: utf-8 -*-
"""Repository pattern for database operations."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .models import User, UserSession, Permission, RolePermission


class UserRepository:
    """Repository for user-related operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email).first()
    
    def get_by_oidc_id(self, oidc_id: str, provider: str) -> Optional[User]:
        """Get user by OIDC ID and provider."""
        return self.db.query(User).filter(
            User.oidc_id == oidc_id,
            User.oidc_provider == provider
        ).first()
    
    def get_all_users(self, skip: int = 0, limit: int = 100, 
                      active_only: bool = True) -> List[User]:
        """Get all users with pagination."""
        query = self.db.query(User)
        if active_only:
            query = query.filter(User.is_active == True)
        return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    def create_user(self, username: str, role: str = "user", 
                   email: Optional[str] = None,
                   password_hash: Optional[str] = None,
                   password_salt: Optional[str] = None,
                   oidc_id: Optional[str] = None,
                   oidc_provider: Optional[str] = None,
                   oidc_email: Optional[str] = None) -> User:
        """Create a new user."""
        user = User(
            username=username,
            role=role,
            email=email,
            password_hash=password_hash,
            password_salt=password_salt,
            oidc_id=oidc_id,
            oidc_provider=oidc_provider,
            oidc_email=oidc_email,
            is_active=True,
            is_verified=(oidc_id is not None),  # OIDC users are verified by provider
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Update user fields."""
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        for key, value in kwargs.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def update_last_login(self, user_id: int) -> None:
        """Update user's last login timestamp."""
        user = self.get_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            self.db.commit()
    
    def delete_user(self, user_id: int) -> bool:
        """Delete a user (soft delete by setting is_active=False)."""
        user = self.get_by_id(user_id)
        if not user:
            return False
        
        user.is_active = False
        user.updated_at = datetime.utcnow()
        self.db.commit()
        return True
    
    def count_users(self, active_only: bool = True) -> int:
        """Count total users."""
        query = self.db.query(User)
        if active_only:
            query = query.filter(User.is_active == True)
        return query.count()
    
    def search_users(self, query_str: str, skip: int = 0, limit: int = 50) -> List[User]:
        """Search users by username or email."""
        search_term = f"%{query_str}%"
        return self.db.query(User).filter(
            or_(
                User.username.like(search_term),
                User.email.like(search_term)
            )
        ).offset(skip).limit(limit).all()


class SessionRepository:
    """Repository for user session operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_session(self, user_id: int, session_token: str, 
                      user_agent: Optional[str] = None,
                      ip_address: Optional[str] = None,
                      expires_at: datetime = None) -> UserSession:
        """Create a new user session."""
        session = UserSession(
            user_id=user_id,
            session_token=session_token,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def get_session(self, session_token: str) -> Optional[UserSession]:
        """Get session by token."""
        return self.db.query(UserSession).filter(
            UserSession.session_token == session_token
        ).first()
    
    def update_session_activity(self, session_token: str) -> bool:
        """Update session last activity time."""
        session = self.get_session(session_token)
        if not session:
            return False
        
        session.last_activity = datetime.utcnow()
        self.db.commit()
        return True
    
    def delete_session(self, session_token: str) -> bool:
        """Delete a session."""
        session = self.get_session(session_token)
        if not session:
            return False
        
        self.db.delete(session)
        self.db.commit()
        return True
    
    def delete_user_sessions(self, user_id: int) -> int:
        """Delete all sessions for a user."""
        result = self.db.query(UserSession).filter(
            UserSession.user_id == user_id
        ).delete()
        self.db.commit()
        return result
    
    def cleanup_expired_sessions(self) -> int:
        """Delete expired sessions."""
        result = self.db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).delete()
        self.db.commit()
        return result


class PermissionRepository:
    """Repository for permission operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_permission(self, permission_id: int) -> Optional[Permission]:
        """Get permission by ID."""
        return self.db.query(Permission).filter(Permission.id == permission_id).first()
    
    def get_permission_by_name(self, name: str) -> Optional[Permission]:
        """Get permission by name."""
        return self.db.query(Permission).filter(Permission.name == name).first()
    
    def get_role_permissions(self, role: str) -> List[Permission]:
        """Get all permissions for a role."""
        return self.db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).filter(
            RolePermission.role == role,
            Permission.enabled == True
        ).all()
    
    def user_has_permission(self, user: User, permission_name: str) -> bool:
        """Check if a user has a specific permission."""
        # Admin users have all permissions
        if user.role == "admin":
            return True
        
        # Check if permission exists and is assigned to user's role
        permission = self.get_permission_by_name(permission_name)
        if not permission or not permission.enabled:
            return False
        
        role_permission = self.db.query(RolePermission).filter(
            RolePermission.role == user.role,
            RolePermission.permission_id == permission.id
        ).first()
        
        return role_permission is not None