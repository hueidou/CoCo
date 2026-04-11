# -*- coding: utf-8 -*-
"""Database session management."""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from ..constant import WORKING_DIR
from .models import Base

# Database configuration
DB_NAME = "coco_users.db"
DB_PATH = WORKING_DIR / DB_NAME
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create parent directory if it doesn't exist
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Use static pool for SQLite to avoid threading issues
    echo=False,  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database by creating all tables."""
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_multi_user_enabled() -> bool:
    """
    Check if multi-user mode is enabled.
    
    Returns:
        bool: Always True (multi-user mode is always enabled)
    """
    return True


def get_database_path() -> Path:
    """
    Get the path to the database file.
    
    Returns:
        Path: Path to the SQLite database file
    """
    return DB_PATH


def database_exists() -> bool:
    """
    Check if the database file exists.
    
    Returns:
        bool: True if database file exists
    """
    return DB_PATH.exists()