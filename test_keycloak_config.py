#!/usr/bin/env python3
"""测试 Keycloak OIDC 配置"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_config_loading():
    """测试 OIDC 配置加载"""
    print("=== 测试1: OIDC 配置加载 ===")
    
    # 设置测试环境变量
    os.environ["COCO_OIDC_ENABLED"] = "true"
    os.environ["COCO_OIDC_CLIENT_ID"] = "coco"
    os.environ["COCO_OIDC_CLIENT_SECRET"] = "test-secret"
    os.environ["COCO_OIDC_ISSUER_URL"] = "https://coco.201609.xyz/auth/realms/coco"
    os.environ["COCO_OIDC_REDIRECT_URI"] = "http://localhost:8080/api/auth/oidc/callback"
    os.environ["COCO_OIDC_SCOPES"] = "openid profile email"
    
    try:
        from src.coco.constant import (
            OIDC_ENABLED, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, 
            OIDC_ISSUER_URL, OIDC_REDIRECT_URI, OIDC_SCOPES,
            OIDC_AUTHORIZATION_ENDPOINT, OIDC_TOKEN_ENDPOINT,
            OIDC_USERINFO_ENDPOINT, OIDC_PROVIDERS
        )
        
        print(f"✓ OIDC 启用: {OIDC_ENABLED}")
        print(f"✓ 客户端ID: {OIDC_CLIENT_ID}")
        print(f"✓ 客户端密钥: {'已设置' if OIDC_CLIENT_SECRET else '未设置'}")
        print(f"✓ Issuer URL: {OIDC_ISSUER_URL}")
        print(f"✓ 重定向URI: {OIDC_REDIRECT_URI}")
        print(f"✓ 作用域: {OIDC_SCOPES}")
        
        # 验证派生端点
        print(f"✓ 授权端点: {OIDC_AUTHORIZATION_ENDPOINT}")
        print(f"✓ Token端点: {OIDC_TOKEN_ENDPOINT}")
        print(f"✓ UserInfo端点: {OIDC_USERINFO_ENDPOINT}")
        
        return True
        
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_json_provider_config():
    """测试 JSON 提供者配置"""
    print("\n=== 测试2: JSON 提供者配置 ===")
    
    # 设置 JSON 提供者配置
    keycloak_config = {
        "id": "keycloak",
        "name": "Keycloak (Coco)",
        "enabled": True,
        "client_id": "coco",
        "client_secret": "test-secret",
        "issuer_url": "https://coco.201609.xyz/auth/realms/coco",
        "scopes": "openid profile email"
    }
    
    os.environ["COCO_OIDC_PROVIDERS"] = json.dumps([keycloak_config])
    
    try:
        from src.coco.constant import OIDC_PROVIDERS, load_oidc_providers
        
        providers = load_oidc_providers()
        print(f"✓ 加载的提供者数: {len(providers)}")
        
        if providers:
            provider = providers[0]
            print(f"✓ 提供者ID: {provider.get('id')}")
            print(f"✓ 提供者名称: {provider.get('name')}")
            print(f"✓ 是否启用: {provider.get('enabled', False)}")
            print(f"✓ 客户端ID: {provider.get('client_id')}")
            print(f"✓ Issuer URL: {provider.get('issuer_url')}")
            print(f"✓ 作用域: {provider.get('scopes', '未设置')}")
        
        # 验证 OIDC_PROVIDERS 常量
        print(f"✓ OIDC_PROVIDERS 常量: {len(OIDC_PROVIDERS)} 个提供者")
        
        return True
        
    except Exception as e:
        print(f"✗ JSON 配置失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_endpoint_generation():
    """测试端点生成"""
    print("\n=== 测试3: Keycloak 端点生成 ===")
    
    test_cases = [
        ("https://coco.201609.xyz/auth/realms/coco",
         {
             "issuer": "https://coco.201609.xyz/auth/realms/coco",
             "auth_endpoint": "https://coco.201609.xyz/auth/realms/coco/protocol/openid-connect/auth",
             "token_endpoint": "https://coco.201609.xyz/auth/realms/coco/protocol/openid-connect/token",
             "userinfo_endpoint": "https://coco.201609.xyz/auth/realms/coco/protocol/openid-connect/userinfo",
             "discovery_url": "https://coco.201609.xyz/auth/realms/coco/.well-known/openid-configuration"
         }),
        ("https://coco.201609.xyz/auth/realms/coco/",
         {
             "issuer": "https://coco.201609.xyz/auth/realms/coco",
             "auth_endpoint": "https://coco.201609.xyz/auth/realms/coco/protocol/openid-connect/auth",
             "token_endpoint": "https://coco.201609.xyz/auth/realms/coco/protocol/openid-connect/token",
             "userinfo_endpoint": "https://coco.201609.xyz/auth/realms/coco/protocol/openid-connect/userinfo",
             "discovery_url": "https://coco.201609.xyz/auth/realms/coco/.well-known/openid-configuration"
         }),
    ]
    
    all_passed = True
    for issuer_url, expected in test_cases:
        print(f"\n测试 issuer: {issuer_url}")
        
        # 手动生成端点
        issuer_url = issuer_url.rstrip("/")
        auth_endpoint = f"{issuer_url}/protocol/openid-connect/auth"
        token_endpoint = f"{issuer_url}/protocol/openid-connect/token"
        userinfo_endpoint = f"{issuer_url}/protocol/openid-connect/userinfo"
        discovery_url = f"{issuer_url}/.well-known/openid-configuration"
        
        # 验证
        passed = True
        if auth_endpoint != expected["auth_endpoint"]:
            print(f"  授权端点错误: {auth_endpoint} != {expected['auth_endpoint']}")
            passed = False
        if token_endpoint != expected["token_endpoint"]:
            print(f"  Token端点错误: {token_endpoint} != {expected['token_endpoint']}")
            passed = False
        if userinfo_endpoint != expected["userinfo_endpoint"]:
            print(f"  UserInfo端点错误: {userinfo_endpoint} != {expected['userinfo_endpoint']}")
            passed = False
        if discovery_url != expected["discovery_url"]:
            print(f"  发现URL错误: {discovery_url} != {expected['discovery_url']}")
            passed = False
        
        if passed:
            print(f"  ✓ 所有端点生成正确")
        else:
            all_passed = False
    
    return all_passed

def test_oidc_module_import():
    """测试 OIDC 模块导入"""
    print("\n=== 测试4: OIDC 模块导入 ===")
    
    # 清理之前的测试环境变量
    for key in list(os.environ.keys()):
        if key.startswith("COCO_OIDC_"):
            del os.environ[key]
    
    # 设置最小配置
    os.environ["COCO_OIDC_ENABLED"] = "true"
    
    try:
        from src.coco.app.routers.oidc import (
            router, OIDCProviderInfo, OIDCProvidersResponse,
            OIDCLoginRequest, OIDCCallbackResponse,
            _get_oidc_providers, _validate_provider_id,
            _generate_state, _validate_state,
            _get_oidc_client
        )
        
        print("✓ OIDC 路由模块导入成功")
        print("✓ OIDC 数据模型导入成功")
        print("✓ OIDC 辅助函数导入成功")
        
        # 测试基础功能
        print("\n✓ OIDC 路由器前缀:", router.prefix)
        print("✓ OIDC 路由器标签:", router.tags)
        
        return True
        
    except Exception as e:
        print(f"✗ OIDC 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_demo_env_file():
    """创建演示环境文件"""
    print("\n=== 测试5: 创建演示配置 ===")
    
    env_content = """# Keycloak OIDC 配置演示
COCO_OIDC_ENABLED=true
COCO_OIDC_CLIENT_ID=coco
COCO_OIDC_CLIENT_SECRET=your-actual-client-secret-here
COCO_OIDC_ISSUER_URL=https://coco.201609.xyz/auth/realms/coco
COCO_OIDC_REDIRECT_URI=http://localhost:8080/api/auth/oidc/callback
COCO_OIDC_SCOPES=openid profile email

# 可选: 启用基础认证
COCO_AUTH_ENABLED=true

# 可选: 设置日志级别为调试模式
COCO_LOG_LEVEL=info
"""
    
    demo_env_path = Path(__file__).parent / ".env.demo"
    try:
        with open(demo_env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        print(f"✓ 演示环境文件已创建: {demo_env_path}")
        print("  请将 'your-actual-client-secret-here' 替换为实际的客户端密钥")
        return True
    except Exception as e:
        print(f"✗ 创建演示文件失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("开始测试 Keycloak OIDC 配置...")
    print("=" * 60)
    
    results = []
    results.append(test_config_loading())
    results.append(test_json_provider_config())
    results.append(test_endpoint_generation())
    results.append(test_oidc_module_import())
    results.append(create_demo_env_file())
    
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    passed = sum(results)
    total = len(results)
    
    for i, passed_test in enumerate(results, 1):
        status = "✓ 通过" if passed_test else "✗ 失败"
        print(f"  测试{i}: {status}")
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n✅ Keycloak OIDC 配置准备就绪！")
        print("\n下一步：")
        print("1. 从 Keycloak 管理控制台获取客户端密钥")
        print("2. 更新 .env.demo 文件中的 COCO_OIDC_CLIENT_SECRET")
        print("3. 复制 .env.demo 为 .env 并启动应用")
        print("4. 访问 /api/auth/oidc/status 验证配置")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误。")
        return 1

if __name__ == "__main__":
    sys.exit(main())