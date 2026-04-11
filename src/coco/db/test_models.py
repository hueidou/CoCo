# -*- coding: utf-8 -*-
"""Quick test to verify database models work correctly."""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Set environment variable to enable multi-user mode for testing
os.environ["COCO_MULTI_USER"] = "true"

from coco.db.session import engine, SessionLocal, init_db
from coco.db.models import User, Permission, RolePermission
from coco.db.repository import UserRepository, PermissionRepository
from coco.auth import _hash_password


def test_database_models():
    """Test basic database operations."""
    print("Testing database models...")
    
    # Initialize database
    init_db()
    print("✓ Database initialized")
    
    # Create a test session
    db = SessionLocal()
    try:
        # Test User model
        user_repo = UserRepository(db)
        
        # Create a test user
        password_hash, password_salt = _hash_password("testpassword123")
        test_user = user_repo.create_user(
            username="testuser",
            email="test@example.com",
            role="user",
            password_hash=password_hash,
            password_salt=password_salt,
            is_verified=True,
        )
        print(f"✓ Test user created: {test_user.username}")
        print(f"  - ID: {test_user.id}")
        print(f"  - Role: {test_user.role}")
        print(f"  - Is admin? {test_user.is_admin}")
        
        # Test retrieval
        retrieved_user = user_repo.get_by_username("testuser")
        assert retrieved_user is not None
        assert retrieved_user.username == "testuser"
        print("✓ User retrieval works")
        
        # Test dictionary conversion (excluding sensitive data)
        user_dict = retrieved_user.to_dict()
        assert "username" in user_dict
        assert "role" in user_dict
        assert "password_hash" not in user_dict
        print("✓ User to_dict() works correctly")
        
        # Test updating user
        updated_user = user_repo.update_user(
            test_user.id,
            email="updated@example.com",
            is_active=False,
        )
        assert updated_user.email == "updated@example.com"
        assert updated_user.is_active == False
        print("✓ User update works")
        
        # Test Permission model
        permission_repo = PermissionRepository(db)
        
        # Create a test permission
        test_perm = Permission(
            name="test.permission",
            description="Test permission",
            enabled=True,
        )
        db.add(test_perm)
        db.commit()
        db.refresh(test_perm)
        print(f"✓ Test permission created: {test_perm.name}")
        
        # Test permission assignment
        role_perm = RolePermission(
            role="user",
            permission_id=test_perm.id,
        )
        db.add(role_perm)
        db.commit()
        print("✓ Role-permission assignment works")
        
        # Test permission checking
        has_permission = permission_repo.user_has_permission(test_user, "test.permission")
        print(f"✓ Permission checking works: user has 'test.permission' = {has_permission}")
        
        # Test admin permission checking
        test_user.role = "admin"
        db.commit()
        has_permission = permission_repo.user_has_permission(test_user, "test.permission")
        assert has_permission == True  # Admin should have all permissions
        print(f"✓ Admin permission checking works: admin has 'test.permission' = {has_permission}")
        
        # Test user search
        users = user_repo.search_users("test")
        assert len(users) > 0
        print(f"✓ User search works: found {len(users)} user(s)")
        
        # Test user count
        count = user_repo.count_users(active_only=False)
        print(f"✓ User count works: {count} total user(s)")
        
        # Clean up test data
        db.query(RolePermission).filter_by(permission_id=test_perm.id).delete()
        db.query(Permission).filter_by(id=test_perm.id).delete()
        db.query(User).filter_by(id=test_user.id).delete()
        db.commit()
        print("✓ Test data cleaned up")
        
        print("\n✅ All database tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()
    
    return True


if __name__ == "__main__":
    success = test_database_models()
    sys.exit(0 if success else 1)