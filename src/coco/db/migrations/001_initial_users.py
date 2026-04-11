# -*- coding: utf-8 -*-
"""Initial database migration for users and permissions."""

import sys
from pathlib import Path

# Add parent directory to path to import models
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from coco.db.models import Base
from coco.db.session import engine


def upgrade():
    """Create initial tables."""
    print("Creating initial database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully")


def downgrade():
    """Drop all tables (for testing/reset purposes)."""
    print("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    print("✓ Database tables dropped")


if __name__ == "__main__":
    # Auto-run upgrade when script is executed directly
    upgrade()