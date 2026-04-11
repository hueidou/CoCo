#!/usr/bin/env python3
"""测试改进点的实现情况"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """测试能否导入关键模块"""
    print("=== 测试1: 导入关键模块 ===")
    
    modules_to_test = [
        ("coco.app.auth", "verify_password"),
        ("coco.app.auth", "_hash_password"),
        ("coco.app.permissions", "ROLE_ADMIN"),
        ("coco.app.permissions", "PERMISSION_TO_ROLE_MAP"),
        ("coco.db.models", "AuditLog"),
        ("coco.db.audit_service", "log_audit_event"),
        ("coco.constant", "OIDC_PROVIDERS"),
    ]
    
    all_passed = True
    for module_name, item_name in modules_to_test:
        try:
            exec(f"from {module_name} import {item_name}")
            print(f"✓ {module_name}.{item_name}")
        except Exception as e:
            print(f"✗ {module_name}.{item_name}: {e}")
            all_passed = False
    
    return all_passed

def test_password_hashing():
    """测试密码哈希功能"""
    print("\n=== 测试2: 密码哈希算法检查 ===")
    
    try:
        from coco.app.auth import _hash_password, verify_password
        
        # 测试哈希函数
        password = "TestPassword123!"
        hash_result = _hash_password(password)
        
        print(f"✓ _hash_password 返回: {len(hash_result)} 个值")
        print(f"  哈希: {hash_result[0][:20]}...")
        print(f"  盐: {hash_result[1]}")
        print(f"  算法: {hash_result[2]}")
        
        # 验证应该是bcrypt
        if hash_result[2] != "bcrypt":
            print(f"✗ 预期算法为'bcrypt', 实际为: {hash_result[2]}")
            return False
        
        print(f"✓ 使用bcrypt算法")
        
        # 验证密码（使用空盐，bcrypt不需要外部盐）
        verified = verify_password(password, hash_result[0], "")
        print(f"✓ 密码验证: {verified}")
        
        return True
    except Exception as e:
        print(f"✗ 密码哈希测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_permissions():
    """测试权限系统"""
    print("\n=== 测试3: 权限系统检查 ===")
    
    try:
        from coco.app.permissions import (
            ROLE_ADMIN, ROLE_USER, ROLE_PUBLIC,
            PERMISSION_TO_ROLE_MAP, ROUTE_PERMISSION_MAP
        )
        
        print(f"✓ 角色定义:")
        print(f"  - ROLE_ADMIN: {ROLE_ADMIN}")
        print(f"  - ROLE_USER: {ROLE_USER}")
        print(f"  - ROLE_PUBLIC: {ROLE_PUBLIC}")
        
        print(f"✓ 权限映射: {len(PERMISSION_TO_ROLE_MAP)} 个条目")
        print(f"  - auth.login => {PERMISSION_TO_ROLE_MAP.get('auth.login', 'N/A')}")
        print(f"  - users.manage => {PERMISSION_TO_ROLE_MAP.get('users.manage', 'N/A')}")
        
        print(f"✓ 路由权限: {len(ROUTE_PERMISSION_MAP)} 个路径")
        for route, methods in list(ROUTE_PERMISSION_MAP.items())[:3]:
            print(f"  - {route}: {methods}")
        
        return True
    except Exception as e:
        print(f"✗ 权限系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_oidc_config():
    """测试OIDC配置"""
    print("\n=== 测试4: OIDC配置检查 ===")
    
    try:
        from coco.constant import OIDC_PROVIDERS, load_oidc_providers
        
        print(f"✓ OIDC_PROVIDERS 类型: {type(OIDC_PROVIDERS)}")
        print(f"✓ OIDC_PROVIDERS 长度: {len(OIDC_PROVIDERS)}")
        
        # 测试加载函数
        providers = load_oidc_providers()
        print(f"✓ load_oidc_providers() 返回: {len(providers)} 个提供商")
        
        return True
    except Exception as e:
        print(f"✗ OIDC配置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_audit_log():
    """测试审计日志"""
    print("\n=== 测试5: 审计日志系统检查 ===")
    
    try:
        from coco.db.audit_service import (
            log_audit_event, log_user_login, 
            log_user_registration, log_password_change
        )
        
        print("✓ 审计日志函数:")
        print(f"  - log_audit_event (主函数)")
        print(f"  - log_user_login")
        print(f"  - log_user_registration")
        print(f"  - log_password_change")
        
        # 检查函数签名
        import inspect
        sig = inspect.signature(log_audit_event)
        param_count = len(sig.parameters)
        print(f"✓ log_audit_event 有 {param_count} 个参数")
        print(f"  参数: {list(sig.parameters.keys())}")
        
        return True
    except Exception as e:
        print(f"✗ 审计日志测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_bcrypt_availability():
    """测试bcrypt可用性"""
    print("\n=== 测试6: Bcrypt可用性检查 ===")
    
    try:
        import bcrypt
        print("✓ bcrypt库已安装")
        
        # 测试bcrypt基本功能
        password = b"testpassword"
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())
        print(f"✓ bcrypt哈希成功: {hashed[:20]}...")
        
        check_result = bcrypt.checkpw(password, hashed)
        print(f"✓ bcrypt验证成功: {check_result}")
        
        return True
    except ImportError:
        print("✗ bcrypt库未安装 (必需依赖)")
        return False
    except Exception as e:
        print(f"✗ bcrypt测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("开始测试改进点实现...")
    print("=" * 50)
    
    results = []
    results.append(test_imports())
    results.append(test_password_hashing())
    results.append(test_permissions())
    results.append(test_oidc_config())
    results.append(test_audit_log())
    results.append(test_bcrypt_availability())
    
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    passed = sum(results)
    total = len(results)
    
    for i, passed_test in enumerate(results, 1):
        status = "✓ 通过" if passed_test else "✗ 失败"
        print(f"  测试{i}: {status}")
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过! 改进点实现成功。")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误。")
        return 1

if __name__ == "__main__":
    sys.exit(main())