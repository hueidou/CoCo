---
name: 多用户和OIDC支持改造
overview: 将CoCo从单用户改为多用户系统，增加角色管理和OIDC支持
design:
  architecture:
    framework: react
  styleKeywords:
    - 现代化管理后台
    - 专业企业级
    - 卡片式布局
    - 响应式设计
    - 深色/浅色主题
  fontSystem:
    fontFamily: PingFang SC
    heading:
      size: 24px
      weight: 600
    subheading:
      size: 18px
      weight: 500
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#1890ff"
      - "#52c41a"
      - "#faad14"
    background:
      - "#ffffff"
      - "#f5f5f5"
      - "#000000"
    text:
      - "#000000e0"
      - "#000000a6"
      - "#00000073"
      - "#ffffff"
    functional:
      - 成功状态
      - 错误状态
      - 警告状态
      - 信息提示
      - 管理员角色标识
      - 普通用户角色标识
todos:
  - id: setup-database-modules
    content: 创建数据库模块和用户数据模型
    status: completed
  - id: add-authlib-dependency
    content: 在pyproject.toml中添加authlib依赖
    status: completed
  - id: modify-jwt-token-structure
    content: 增强JWT token包含用户ID和角色信息
    status: completed
    dependencies:
      - setup-database-modules
  - id: create-permission-middleware
    content: 创建基于角色的权限检查中间件
    status: completed
    dependencies:
      - modify-jwt-token-structure
  - id: implement-oidc-routes
    content: 实现OIDC认证路由和回调处理
    status: completed
    dependencies:
      - add-authlib-dependency
  - id: update-auth-routes
    content: 更新认证路由API支持多用户注册
    status: completed
    dependencies:
      - modify-jwt-token-structure
  - id: create-user-management-api
    content: 创建用户管理API端点
    status: completed
    dependencies:
      - setup-database-modules
  - id: modify-frontend-auth-api
    content: 更新前端认证API类型和函数
    status: completed
    dependencies:
      - update-auth-routes
  - id: create-admin-user-interface
    content: 创建用户管理界面组件
    status: completed
    dependencies:
      - create-user-management-api
  - id: update-login-page-oidc
    content: 更新登录页面支持OIDC登录
    status: completed
    dependencies:
      - implement-oidc-routes
  - id: add-api-permission-decorators
    content: 为现有API端点添加权限装饰器
    status: completed
    dependencies:
      - create-permission-middleware
  - id: create-migration-script
    content: 创建单用户到多用户数据迁移脚本
    status: completed
    dependencies:
      - setup-database-modules
  - id: test-multi-user-flow
    content: 使用[subagent:code-explorer]测试多用户登录流程
    status: completed
    dependencies:
      - update-auth-routes
      - modify-frontend-auth-api
  - id: test-oidc-integration
    content: 测试OIDC认证集成
    status: completed
    dependencies:
      - implement-oidc-routes
      - update-login-page-oidc
  - id: verify-permission-control
    content: 验证角色权限控制功能
    status: completed
    dependencies:
      - add-api-permission-decorators
      - create-admin-user-interface
---

## 产品概述

将现有的单用户认证系统扩展为支持多用户的系统，增加管理员和普通用户角色，并集成通用OIDC认证。系统完成后将支持Keycloak等标准OIDC提供商的对接。

## 核心功能

1. **多用户支持**：支持多个用户注册和登录，每个用户有独立的数据空间
2. **角色系统**：提供admin和user两种角色

- admin：全局配置权限、用户管理、所有功能访问权限
- user：聊天、频道、会话、定时任务（执行）、智能体管理（只查看）

3. **OIDC集成**：支持通用OpenID Connect认证
4. **权限控制**：基于角色的API访问控制，保护敏感操作
5. **用户管理**：管理员可以管理用户（创建、删除、修改角色）

## 技术栈选择

- **后端**：Python + FastAPI（现有技术栈）
- **OIDC库**：authlib（标准OIDC客户端库，需添加到依赖）
- **数据库**：SQLite + SQLAlchemy（轻量级，适合多用户数据存储）
- **JWT扩展**：增强JWT token包含用户ID和角色信息

## 实现方案

### 总体策略

1. **增量迁移**：保持现有auth.json文件格式，增加users.db数据库存储多用户信息
2. **向后兼容**：通过环境变量控制多用户模式（COCO_MULTI_USER），默认保持单用户
3. **权限分层**：在现有认证中间件后添加角色检查中间件
4. **OIDC可选**：OIDC认证作为可选功能，可与本地认证共存

### 关键实现细节

1. **JWT增强**：修改create_token和verify_token函数，在token payload中添加user_id和role字段
2. **数据库设计**：SQLite表包含users表（id, username, password_hash, password_salt, role, oidc_id, email等）
3. **权限检查**：创建permission装饰器和中间件，为API端点标注所需角色
4. **数据隔离**：普通用户只能访问自己的聊天、会话等数据

### 性能与安全

- 用户认证信息内存缓存（5分钟TTL）
- OIDC令牌验证使用缓存避免重复请求
- 密码哈希保持现有SHA256盐值算法
- 关键操作审计日志记录

## 实现注意事项

### 向后兼容性

- 默认启用单用户模式，通过COCO_MULTI_USER=true启用多用户
- 现有auth.json继续存储JWT密钥，用户数据迁移到数据库
- 单用户模式下的现有用户自动成为admin

### OIDC配置

- 通过环境变量配置OIDC提供商（CLIENT_ID, CLIENT_SECRET, ISSUER_URL）
- 支持标准授权码流程
- OIDC用户自动映射到本地用户账户

### 权限粒度

1. **admin权限**：系统配置、用户管理、所有数据访问
2. **user权限**：个人聊天、频道消息、定时任务执行、智体查看
3. **公共权限**：登录、注册（如启用）、OIDC回调

## 目录结构

```
d:/workspace/CoCo/
├── src/coco/
│   ├── app/
│   │   ├── auth.py                            # [MODIFY] 修改为多用户认证，增强JWT
│   │   ├── permissions.py                     # [NEW] 权限装饰器和角色检查
│   │   ├── routers/
│   │   │   ├── auth.py                        # [MODIFY] 扩展认证API，支持多用户注册
│   │   │   ├── users.py                       # [NEW] 用户管理API（仅admin）
│   │   │   ├── oidc.py                        # [NEW] OIDC认证路由
│   │   │   └── __init__.py                    # [MODIFY] 注册新路由
│   │   └── middleware/
│   │       ├── __init__.py                    # [NEW] 中间件包
│   │       └── permission_middleware.py       # [NEW] 权限检查中间件
│   ├── db/
│   │   ├── __init__.py                        # [NEW] 数据库初始化
│   │   ├── models.py                          # [NEW] SQLAlchemy ORM模型
│   │   ├── session.py                         # [NEW] 数据库会话管理
│   │   └── migrations/                        # [NEW] 数据库迁移脚本
│   │       └── 001_initial_users.py
│   └── constant.py                            # [MODIFY] 新增配置常量
├── console/src/
│   ├── api/modules/
│   │   ├── auth.ts                            # [MODIFY] 更新认证API
│   │   ├── users.ts                           # [NEW] 用户管理API类型和函数
│   │   └── oidc.ts                            # [NEW] OIDC认证API
│   ├── pages/
│   │   ├── Admin/
│   │   │   └── Users/                         # [NEW] 用户管理页面
│   │   │       ├── index.tsx
│   │   │       ├── UserList.tsx
│   │   │       └── UserForm.tsx
│   │   └── Login/
│   │       └── index.tsx                      # [MODIFY] 支持OIDC登录按钮
│   └── components/
│       └── RoleGuard/                         # [NEW] 角色权限守卫组件
│           ├── index.tsx
│           └── types.ts
└── scripts/
    └── migrate_to_multi_user.py              # [NEW] 单用户到多用户迁移脚本
```

## 关键代码结构

### 用户模型

```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String)
    password_salt = Column(String)
    role = Column(String, default="user")  # "admin" or "user"
    oidc_id = Column(String)  # OIDC provider user ID
    oidc_provider = Column(String)  # e.g., "keycloak"
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
```

### 权限装饰器

```python
def require_role(role: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user_role = request.state.user_role
            if user_role != role and user_role != "admin":
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
```

## 设计风格

采用现代化的管理后台设计风格，保持现有界面的一致性和专业性。针对多用户和角色管理功能，设计清晰直观的管理界面。

### 设计美学

1. **专业管理界面**：采用与现有console一致的深色/浅色主题切换
2. **视觉层次**：卡片式布局区分不同功能模块，表格操作区域明确
3. **状态标识**：使用颜色标签区分用户角色（admin紫色、user青色）
4. **交互友好**：操作按钮分组，重要操作需要二次确认

### 页面规划

#### 1. 增强登录页面

- 保持现有本地登录表单
- 新增OIDC登录按钮区域（显示已配置的提供商）
- 登录方式切换标签页
- 首次注册引导提示

#### 2. 用户管理页面（仅admin可见）

- 用户列表表格，支持搜索、筛选、分页、排序
- 用户操作工具栏（添加、导入、批量操作）
- 用户详情编辑表单
- 用户操作日志查看面板

#### 3. 角色权限说明页面

- 权限矩阵表格展示不同角色的功能访问权限
- 权限申请流程说明（如需要扩展权限）

### 模块设计

#### 登录页面增强模块

- **OIDC登录按钮区**：显示已配置的OIDC提供商按钮，支持图标显示
- **本地登录表单区**：现有登录表单保持不变
- **登录方式切换**：选项卡或按钮切换不同登录方式
- **首次使用引导**：无用户时的注册引导提示

#### 用户管理表格模块

- **搜索和筛选工具栏**：用户名、角色、邮箱、状态多条件筛选
- **批量操作区**：选择用户后启用的批量操作按钮
- **分页表格**：每页显示20条记录，支持自定义分页大小
- **行内操作列**：编辑、删除、重置密码、查看详情操作

#### 用户表单模块

- **基本信息卡片**：用户名、邮箱、角色选择（admin/user）
- **认证方式卡片**：显示本地密码状态和OIDC绑定信息
- **操作历史卡片**：最近登录时间和操作记录
- **表单操作按钮组**：保存、取消、删除（危险操作需要确认）

#### 权限守卫组件

- **路由守卫**：根据用户角色控制页面访问权限
- **组件级权限**：控制界面元素的显示/隐藏
- **操作权限检查**：按钮点击前的权限验证
- **无权限提示**：友好提示用户权限不足，引导申请或联系管理员

## 代理扩展

### SubAgent

- **code-explorer**
- 目的：在实现过程中帮助搜索和理解现有代码结构，特别是在修改现有认证和路由时快速定位相关代码
- 预期结果：确保对现有系统的修改不会破坏现有功能，理解现有数据流动和认证机制

### Skill

- **find-skills**
- 目的：如果在实现过程中遇到未知的第三方库集成需求，帮助查找相关技能
- 预期结果：为OIDC集成或数据库操作提供最佳实践建议