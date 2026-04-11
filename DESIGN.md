# CoCo 多用户与认证系统设计文档

## 1. 概述

CoCo 系统从单用户模式扩展为完整的多用户平台，实现了基于角色的访问控制（RBAC）、OIDC 认证集成、会话数据隔离和企业级用户管理。本文档描述所有相关改进的架构设计、实现细节和部署指南。

### 1.1 核心变更

| 改进项 | 说明 |
|--------|------|
| OIDC 认证集成 | 对接 Keycloak 等标准 OIDC 提供商，实现 SSO 登录 |
| 多用户 RBAC | 两级角色体系（admin/user），中间件自动发现 + 白名单驱动权限控制 |
| 会话数据隔离 | 统一 `user_id` 模型，后端从 JWT 凭证提取，客户端不可伪造 |
| 纯多用户模式 | 移除单用户向后兼容，`MULTI_USER_ENABLED` 硬编码为 `True` |
| 密码安全升级 | 移除 SHA-256 兼容，统一使用 bcrypt（成本因子 12） |
| 审计日志 | 数据库级审计记录，覆盖登录/注册/密码变更等操作 |
| copaw → coco 重命名 | 全项目品牌和命名空间迁移 |

### 1.2 设计原则

- **认证委托**：本地登录/注册/密码管理全部禁用（HTTP 410），统一由 OIDC 提供商管理
- **中间件驱动**：权限控制在中间件层集中执行，而非分散的装饰器
- **服务端权威**：`user_id` 由 `AuthMiddleware` 从 JWT 的 `sub` 字段提取，客户端无法伪造
- **软删除**：用户删除采用 `is_active=False` 软删除，保留数据完整性

---

## 2. 系统架构

### 2.1 请求处理流程

```
客户端请求
  │
  ▼
AuthMiddleware ── 提取 JWT → 设置 request.state.user / user_id / user_role
  │
  ▼
PermissionMiddleware ── 自动发现路由 + 白名单匹配 → 校验角色层级
  │
  ▼
Router ── 业务逻辑 → Repository → SQLAlchemy → SQLite
```

### 2.2 OIDC 认证流程

```
1. 前端 → POST /api/auth/oidc/login  → 返回 authorization_url + state
2. 浏览器 → 重定向到 OIDC 提供商
3. 用户在 OIDC 提供商完成认证
4. OIDC 提供商 → GET /api/auth/oidc/callback?code=xxx&state=xxx
5. 后端 → 用 code 换取 token → 获取 userinfo → 同步/创建本地用户 → 签发 CoCo JWT
6. 后端 → 重定向到前端 /login/callback?token=xxx
```

### 2.3 数据隔离模型

所有资源（Chat、CronJob 等）通过统一的 `user_id` (str) 字段实现用户数据隔离。

| 来源 | `user_id` 值 | 说明 |
|------|-------------|------|
| Console 渠道 | JWT `sub` 字段（用户名） | 由 `AuthMiddleware` 设置在 `request.state.user`，后端直接使用，前端不传递 |
| 其他渠道（飞书/钉钉/Telegram） | 渠道发送者 ID（如 open_id） | 由渠道适配器设置，不在认证系统中 |

**不支持匿名访问。** 未认证请求在 `AuthMiddleware` 层即被拒绝（401）。`ownership.py` 中 `get_caller_identity` 对未认证请求直接抛出 403。

关键规则：**Console 渠道的 `user_id` 由后端从 JWT 凭证提取，前端不传递任何用户标识。** 这确保了用户身份不可伪造。

---

## 3. 后端模块设计

### 3.1 认证模块 (`src/coco/app/auth.py`)

**核心职责：** 密码哈希、JWT 签发/验证、认证中间件

| 组件 | 说明 |
|------|------|
| `_hash_password(password, salt)` | bcrypt 哈希，成本因子 12，返回 `(hash, "", "bcrypt")` |
| `verify_password(password, stored_hash, salt)` | bcrypt 验证 |
| `create_token(username, user_id, role)` | HMAC-SHA256 签名，格式 `base64(payload).signature`，包含 `sub/exp/iat/uid/role` |
| `verify_token(token, return_dict)` | 验证签名和过期，返回用户名或完整信息字典 |
| `AuthMiddleware` | Starlette 中间件，强制 Bearer token 认证，设置 `request.state.user/user_id/user_role/user_info` |

**公共路径豁免：** `/api/auth/status`、`/api/auth/oidc/*` 等路径无需认证。本地请求（localhost）在 `COCO_AUTH_ENABLED` 未开启时跳过认证。

**JWT 密钥管理：** 密钥存储在 `auth.json`（加密），由 `secret_store` 模块加解密，文件权限 `0o600`。

### 3.2 权限模块 (`src/coco/app/permissions.py`)

**核心职责：** 自动发现路由级 RBAC 执行

**角色层级：**

```
admin (2) → 继承 user (1)
```

> 注意：系统不支持匿名访问，已移除 public 层级。

**权限策略：** 自动发现 + 白名单

`PermissionMiddleware` 在首次请求时自动扫描所有 FastAPI 路由，根据 HTTP 方法分配默认权限：

| 规则 | 说明 |
|------|------|
| 写操作 (POST/PUT/DELETE/PATCH) | 默认需要 admin 角色 |
| 读操作 (GET) | 默认需要 user 角色 |
| 公共路径 (`/api/auth/*`, `/api/version`) | 无需认证 |
| 用户可写白名单 | 特定写操作降级为 user 角色 |

**用户可写白名单** (`_USER_WRITABLE_ROUTES`)：

以下写操作对 user 角色开放（完整列表见 `permissions.py`）：

| 类别 | 端点 | 方法 |
|------|------|------|
| 控制台聊天 | `/api/console/chat` | POST |
| 控制台聊天 | `/api/console/chat/stop` | POST |
| 控制台聊天 | `/api/console/upload` | POST |
| 聊天管理 | `/api/chats` | POST |
| 聊天管理 | `/api/chats/batch-delete` | POST |
| 聊天管理 | `/api/chats/{chat_id}` | PUT/DELETE |
| 定时任务 | `/api/cron/jobs` | POST |
| 定时任务 | `/api/cron/jobs/{job_id}` | PUT/DELETE |
| 定时任务 | `/api/cron/jobs/{job_id}/pause\|resume\|run` | POST |
| 消息发送 | `/api/messages/send` | POST |
| 用户偏好 | `/api/config/user-timezone` | PUT |
| UI 偏好 | `/api/settings/language` | PUT |
| 工作区 | `/api/workspace/upload` | POST |

以上路由在 agent-scoped 前缀 (`/api/agents/{agentId}/...`) 下有等效路径，同样适用白名单。

**admin 专属端点**（不在白名单中，所有写操作需 admin 角色）：

| 模块 | 说明 |
|------|------|
| Skills | 技能模块对 user 角色完全不可见 |
| Agent 工作区文件 | `PUT /api/agents/{agentId}/files/{filename}` 为 admin 专属 |
| Providers/Models | LLM 提供商和模型配置 |
| Channels | 渠道配置写入 |
| Users | 用户管理 CRUD |
| Security | 安全配置 |
| Tools | 工具管理 |

**无装饰器设计：** `@require_role`、`@require_permission`、`@require_admin`、`@require_user` 装饰器已全部移除。权限执行完全由 `PermissionMiddleware` 中间件集中处理，路由文件无需任何权限相关代码。

### 3.3 OIDC 路由 (`src/coco/app/routers/oidc.py`)

**端点：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/auth/oidc/providers` | GET | 列出已配置的 OIDC 提供商 |
| `/auth/oidc/login` | POST | 发起 OIDC 登录，返回 `authorization_url` + `state` |
| `/auth/oidc/callback` | GET | 处理 OIDC 回调，交换 code → 创建/同步用户 → 签发 JWT → 重定向前端 |
| `/auth/oidc/status` | GET | 返回 OIDC 配置状态 |

**用户同步逻辑 (`_sync_or_create_user_from_oidc`)：**
1. 按 `oidc_id`（格式 `{provider_id}:{sub}`）查找本地用户
2. 若未找到，按 email 查找
3. 若仍未找到，按 username 查找
4. 都未找到则创建新用户，默认角色为 `user`（第一个用户为 `admin`）

**CSRF 防护：** 使用 `state` 参数，10 分钟过期，存储在内存字典中（生产环境建议用 Redis）。

**多提供商支持：** 通过环境变量 `OIDC_PROVIDERS`（JSON 数组）配置多个提供商，每个包含 `id`、`name`、`issuer_url`、`client_id`、`client_secret`。

### 3.4 认证路由 (`src/coco/app/routers/auth.py`)

| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/auth/login` | POST | **410 Gone** | 本地登录已禁用，使用 OIDC |
| `/auth/register` | POST | **410 Gone** | 本地注册已禁用，使用 OIDC |
| `/auth/status` | GET | 正常 | 返回认证配置状态 |
| `/auth/verify` | GET | 正常 | 验证 Bearer token 有效性 |
| `/auth/update-profile` | POST | **410 Gone** | 个人资料管理已委托给 Keycloak |

HTTP 410 (Gone) 明确表示这些端点曾经存在，现已永久移除。

### 3.5 用户管理路由 (`src/coco/app/routers/users.py`)

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/users/` | GET | admin | 分页用户列表 |
| `/users/{user_id}` | GET | admin | 获取单个用户 |
| `/users/` | POST | admin | 创建用户（验证唯一性、密码强度≥6位） |
| `/users/{user_id}` | PUT | admin | 更新用户字段 |
| `/users/{user_id}` | DELETE | admin | 软删除（`is_active=False`） |
| `/users/{user_id}/reset-password` | POST | admin | 重置密码 |
| `/users/me` | GET | user | 获取当前用户信息 |

### 3.6 数据所有权 (`src/coco/app/ownership.py`)

| 函数 | 说明 |
|------|------|
| `get_caller_identity(request)` | 从 `request.state.user` 提取 `(user_id, role)` |
| `filter_by_user(user_id, role, items)` | admin 看全部，非 admin 仅看自己的 |
| `require_user_access(user_id, role, resource_user_id)` | 无权限则抛 HTTP 403 |

在 `src/coco/app/runner/api.py` 中的应用：
- **列表**：非 admin 用户设置 `user_filter = caller_id`
- **创建**：`user_id` 优先使用 `caller_id`（来自 JWT），回退到请求体中的值
- **读取/更新/删除**：先调用 `require_user_access()` 校验所有权

在 `src/coco/app/routers/console.py` 中的应用：
- `_extract_session_and_payload` 从 `request.state.user` 获取 `sender_id`，不从请求体读取
- 前端不传递 `user_id`，完全由后端从认证凭证确定

### 3.7 数据库模块 (`src/coco/db/`)

#### 3.7.1 数据模型 (`models.py`)

| 模型 | 表名 | 关键字段 |
|------|------|----------|
| `User` | `users` | id, username, password_hash, password_salt, role, email, oidc_id, oidc_provider, oidc_email, is_active, is_verified, created_at, updated_at, last_login |
| `UserSession` | `user_sessions` | id, user_id, session_token, user_agent, ip_address, expires_at, last_activity |
| `Permission` | `permissions` | id, name (unique), description, enabled |
| `RolePermission` | `role_permissions` | id, role, permission_id |
| `AuditLog` | `audit_logs` | id, user_id, username, event_type, event_action, event_description, ip_address, user_agent, success, additional_data (JSON) |

#### 3.7.2 仓储层 (`repository.py`)

| 仓储 | 关键方法 |
|------|----------|
| `UserRepository` | get_by_id, get_by_username, get_by_email, get_by_oidc_id, get_all_users(分页), create_user, update_user, update_last_login, delete_user(软删除), count_users, search_users |
| `SessionRepository` | create_session, get_session, update_session_activity, delete_session, delete_user_sessions, cleanup_expired_sessions |
| `PermissionRepository` | get_permission, get_permission_by_name, get_role_permissions, user_has_permission（admin 绕过所有检查） |

#### 3.7.3 数据库初始化 (`initializer.py`)

- `initialize_database()`：创建表结构 → 种子权限 → 确保管理员存在
- `create_default_permissions(db)`：37 个默认权限，覆盖 system/users/agents/chats/channels/cron/skills/providers，admin 授予全部，user 授予有限子集
- `create_default_admin_user(db)`：若无管理员则自动创建，密码随机生成并输出警告日志
- `migrate_single_user_to_multi_user()`：从 `auth.json` 迁移单用户为管理员（幂等）

#### 3.7.4 审计服务 (`audit_service.py`)

| 函数 | 事件类型 |
|------|----------|
| `log_user_login` | login / failed_login |
| `log_user_registration` | user_created |
| `log_password_change` | password_change |
| `log_user_update` | user_updated |

> 注意：审计服务已创建但尚未在路由处理器中集成调用，需后续接入。

---

## 4. 前端设计

### 4.1 登录页 (`console/src/pages/Login/index.tsx`)

- 无用户名/密码表单，完全 OIDC 化
- 动态发现并渲染已配置的 OIDC 提供商按钮（Google/GitHub/通用图标）
- 点击提供商按钮 → `authApi.oidc.login()` → 获取 `authorization_url` → 浏览器重定向
- `state` 存入 `localStorage` 用于 CSRF 防护
- 支持 `redirect` 查询参数，登录后跳转到目标页面
- 认证未启用时直接跳转 `/chat`

### 4.2 用户管理页 (`console/src/pages/Settings/Users/`)

**index.tsx：**
- 非 admin 用户显示 "Access Denied"
- 当前用户通过 `authApi.verify(token)` 识别
- 不允许编辑/删除自身账户
- 不允许删除 admin 角色用户
- 密码重置生成随机临时密码，仅显示一次
- 删除为软删除，保留数据

**UserForm.tsx：**
- 创建/编辑双模式
- 角色选择：User / Administrator
- 活跃/停用开关
- 编辑时密码可选（留空保持原密码）
- 用户名验证：≥3 字符，仅字母数字/点/连字符/下划线

### 4.3 侧边栏 (`console/src/layouts/Sidebar.tsx`)

- 从 JWT 解析 `role`，失败则调用 `authApi.verify()` 回退
- 非 admin 用户可见菜单：`chat`、`channels`、`sessions`、`cron-jobs`
- 菜单项递归过滤：组内子项过滤后若为空则移除整个组
- 底部显示当前用户名、角色和登出按钮

### 4.4 路由守卫 (`console/src/layouts/MainLayout/index.tsx`)

- `AdminRoute` 组件：非 admin 角色显示 403 页面
- Admin 专属路由：`/heartbeat`、`/skills`、`/skill-pool`、`/tools`、`/mcp`、`/workspace`、`/agent-config`、`/agents`、`/models`、`/environments`、`/security`、`/token-usage`、`/voice-transcription`
- 开放路由：`/chat`、`/sessions`、`/cron-jobs`、`/channels`

### 4.5 前端认证三层防护

```
1. 认证层（Login 页面）── OIDC SSO 入口
2. 导航层（Sidebar）── 隐藏无权限菜单项
3. 路由层（AdminRoute）── 阻止直接 URL 访问
```

### 4.6 API 模块

**auth.ts：** 定义 `LoginResponse`、`AuthStatusResponse`、`VerifyResponse`、OIDC 相关类型和 API 方法（`authApi.oidc.login/getProviders/getStatus`）

**users.ts：** 定义 `User` 接口（含 `oidc_provider` 字段），CRUD API，`isAdmin()`、`formatRole()` 辅助函数

---

## 5. 环境配置

### 5.1 核心环境变量

```bash
# 认证开关
COCO_AUTH_ENABLED=true

# 单提供商配置（"default" 提供商）
COCO_OIDC_ENABLED=true
COCO_OIDC_CLIENT_ID=coco
COCO_OIDC_CLIENT_SECRET=<from-keycloak>
COCO_OIDC_ISSUER_URL=https://coco.201609.xyz/auth/realms/coco
COCO_OIDC_REDIRECT_URI=http://localhost:8080/api/auth/oidc/callback
COCO_OIDC_SCOPES=openid profile email

# 多提供商配置（JSON 格式）
OIDC_PROVIDERS=[{"id":"keycloak","name":"Keycloak","issuer_url":"...","client_id":"...","client_secret":"..."}]
```

### 5.2 自动派生的 OIDC 端点

基于 `COCO_OIDC_ISSUER_URL` 自动生成：
- 授权端点：`{issuer_url}/protocol/openid-connect/auth`
- Token 端点：`{issuer_url}/protocol/openid-connect/token`
- UserInfo 端点：`{issuer_url}/protocol/openid-connect/userinfo`
- 发现 URL：`{issuer_url}/.well-known/openid-configuration`

### 5.3 Keycloak 客户端要求

- 访问类型：`confidential`
- 重定向 URI：包含 `http://localhost:8080/api/auth/oidc/callback`
- 启用标准流程

---

## 6. 数据库设计

### 6.1 存储引擎

SQLite（`{WORKING_DIR}/coco_users.db`），使用 SQLAlchemy 的 `StaticPool` + `check_same_thread=False` 确保线程安全。

### 6.2 ER 关系

```
User 1──* UserSession
User 1──* AuditLog

Permission *──* Role (通过 RolePermission)
```

### 6.3 种子权限

`initializer.py` 创建 37 个默认权限，按类别：

| 类别 | 权限数 | 示例 |
|------|--------|------|
| system | 5 | system.config.read, system.config.write |
| users | 5 | users.list, users.create, users.manage |
| agents | 4 | agents.list, agents.create |
| chats | 4 | chats.access, chats.create |
| channels | 4 | channels.list, channels.manage |
| cron | 4 | cron.list, cron.manage |
| skills | 4 | skills.list, skills.manage |
| providers | 4 | providers.list, providers.manage |

admin 授予全部权限；user 授予有限子集（查看/创建聊天、查看频道等）。

---

## 7. 安全设计

### 7.1 密码存储

- 算法：bcrypt，成本因子 12
- 盐：内嵌于 bcrypt 哈希中（`password_salt` 字段保留为空字符串）
- SHA-256 兼容已移除，旧用户需重置密码

### 7.2 JWT 设计

- 算法：HMAC-SHA256（无外部 JWT 库依赖）
- 格式：`base64(payload).signature`
- 载荷：`sub`（用户名）、`exp`（过期时间）、`iat`（签发时间）、`uid`（用户 ID）、`role`（角色）
- 密钥：存储于 `auth.json`（加密），文件权限 `0o600`

### 7.3 数据隔离

- 统一标识：`user_id` (str)，Console 渠道来自 JWT `sub`，其他渠道来自发送者 ID
- admin 角色可查看所有用户数据
- 非 admin 仅能访问 `user_id == caller_id` 的数据
- Console 渠道的 `user_id` 由后端从 JWT 凭证提取，前端不传递
- 创建会话时 `user_id` 优先使用认证凭证中的值，忽略客户端传入值
- 非 Console 渠道（飞书/钉钉/Telegram）不在认证系统中，其聊天在认证模式下仅 admin 可见
- 不支持匿名访问，未认证请求在 AuthMiddleware 层即被拒绝

### 7.4 CSRF 防护

OIDC 登录流程使用 `state` 参数，10 分钟有效期，一次性消耗。

---

## 8. 迁移指南

### 8.1 新安装

1. 配置 `.env` 文件（参照 `.env.example`）
2. 启动服务，数据库自动初始化
3. 第一个通过 OIDC 登录的用户自动成为 admin

### 8.2 从单用户模式迁移

1. 运行 `migrate_single_user_to_multi_user()`（应用启动时自动执行）
2. `auth.json` 中的用户凭据迁移到 `coco_users.db` 为 admin
3. `auth.json` 此后仅存储 JWT 密钥

### 8.3 环境变量变更

| 变量 | 旧行为 | 新行为 |
|------|--------|--------|
| `COCO_MULTI_USER` | 控制是否启用多用户 | **已废弃**，始终为 True |
| `COCO_AUTH_ENABLED` | 控制认证 | 保持不变 |
| `COCO_OIDC_ENABLED` | 无 | 新增，控制 OIDC |

---

## 9. 文件结构

```
src/coco/
├── app/
│   ├── auth.py                    # 认证中间件、密码哈希、JWT
│   ├── permissions.py             # RBAC 权限中间件
│   ├── ownership.py               # 数据所有权控制
│   ├── routers/
│   │   ├── auth.py                # 认证端点（本地登录已禁用）
│   │   ├── oidc.py                # OIDC 认证路由
│   │   └── users.py               # 用户管理 CRUD API
├── db/
│   ├── __init__.py                # 导出 SessionLocal, UserRepository 等
│   ├── models.py                  # User, UserSession, Permission, RolePermission, AuditLog
│   ├── repository.py              # UserRepository, SessionRepository, PermissionRepository
│   ├── session.py                 # SQLAlchemy 引擎和会话工厂
│   ├── initializer.py             # 数据库初始化和种子数据
│   ├── audit_service.py           # 审计日志服务
│   └── migrations/                # 数据库迁移脚本
├── constant.py                    # OIDC 配置常量、MULTI_USER_ENABLED

console/src/
├── api/modules/
│   ├── auth.ts                    # 认证 API 和 OIDC 子模块
│   └── users.ts                   # 用户管理 API
├── pages/
│   ├── Login/index.tsx            # OIDC 登录页
│   └── Settings/Users/            # 用户管理页（index.tsx + UserForm.tsx）
├── layouts/
│   ├── Sidebar.tsx                # 角色过滤的侧边栏
│   ├── MainLayout/index.tsx       # AdminRoute 路由守卫
│   └── constants.ts               # 导航键-路径映射
```

---

## 10. 已知限制与后续规划

### 10.1 已知限制

| 项 | 说明 |
|----|------|
| OIDC state 存储 | 内存字典，重启丢失，生产环境需用 Redis |
| 审计日志未集成 | `audit_service` 已创建但未在路由中调用 |
| 客户端搜索 | 用户搜索为前端过滤，大数据量时需后端搜索端点 |
| 令牌刷新 | 暂未实现 OIDC refresh token 逻辑 |

### 10.2 后续规划

1. 将 OIDC state 存储迁移到 Redis
2. 在 auth/oidc/users 路由中集成审计日志
3. 实现后端用户搜索端点
4. 支持 OIDC refresh token 和自动续签
5. 用户组和部门管理
6. 双因素认证（2FA）
7. SAML 集成
8. 实时权限变更通知
