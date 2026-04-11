# -*- coding: utf-8 -*-
"""Audit logging service for tracking important system events."""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from .models import AuditLog
from .session import SessionLocal

logger = logging.getLogger(__name__)


def log_audit_event(
    event_type: str,
    event_action: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    event_description: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    additional_data: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> bool:
    """Log an audit event to the database.
    
    Args:
        event_type: Type of event (e.g., "login", "register", "password_change")
        event_action: Specific action (e.g., "successful_login", "user_created")
        user_id: ID of the user who performed the action
        username: Username for easier reference
        event_description: Human-readable description
        ip_address: Client IP address
        user_agent: Client user agent string
        success: Whether the operation was successful
        additional_data: Any additional context data (will be stored as JSON)
        db: Database session (will create one if not provided)
    
    Returns:
        True if logged successfully, False otherwise
    """
    should_close_db = False
    
    try:
        # Use provided session or create a new one
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        # Prepare additional data as JSON string
        additional_data_json = None
        if additional_data:
            try:
                additional_data_json = json.dumps(additional_data)
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to serialize additional data for audit log: {e}")
        
        # Create audit log entry
        audit_log = AuditLog(
            user_id=user_id,
            username=username,
            event_type=event_type,
            event_action=event_action,
            event_description=event_description,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            additional_data=additional_data_json,
            created_at=datetime.utcnow(),
        )
        
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        
        logger.debug(f"Audit event logged: {event_type}.{event_action} user={username}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")
        if db and should_close_db:
            try:
                db.rollback()
            except Exception:
                pass
        return False
        
    finally:
        if should_close_db and db:
            try:
                db.close()
            except Exception:
                pass


def log_user_login(
    user_id: int,
    username: str,
    success: bool,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    auth_method: str = "password",
    failure_reason: Optional[str] = None,
) -> bool:
    """Log user login attempt."""
    event_action = "successful_login" if success else "failed_login"
    event_description = f"{'Successful' if success else 'Failed'} login via {auth_method}"
    
    additional_data = {
        "auth_method": auth_method,
    }
    
    if failure_reason:
        additional_data["failure_reason"] = failure_reason
    
    return log_audit_event(
        event_type="login",
        event_action=event_action,
        user_id=user_id,
        username=username,
        event_description=event_description,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        additional_data=additional_data,
    )


def log_user_registration(
    user_id: int,
    username: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """Log user registration."""
    return log_audit_event(
        event_type="register",
        event_action="user_created",
        user_id=user_id,
        username=username,
        event_description=f"User {username} registered",
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
    )


def log_password_change(
    user_id: int,
    username: str,
    success: bool,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """Log password change attempt."""
    event_action = "password_changed" if success else "password_change_failed"
    event_description = f"{'Successful' if success else 'Failed'} password change"
    
    return log_audit_event(
        event_type="password_change",
        event_action=event_action,
        user_id=user_id,
        username=username,
        event_description=event_description,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
    )


def log_user_update(
    user_id: int,
    username: str,
    updated_by_user_id: Optional[int] = None,
    updated_by_username: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """Log user profile update."""
    event_action = "user_updated"
    event_description = f"User {username} profile updated"
    
    additional_data = {"changes": changes}
    if updated_by_user_id:
        additional_data["updated_by_user_id"] = updated_by_user_id
    if updated_by_username:
        additional_data["updated_by_username"] = updated_by_username
    
    return log_audit_event(
        event_type="user_update",
        event_action=event_action,
        user_id=user_id,
        username=username,
        event_description=event_description,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
        additional_data=additional_data,
    )