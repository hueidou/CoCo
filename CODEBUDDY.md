# CODEBUDDY.md

本文件为 CodeBuddy Code 在本仓库中工作时提供指导。

## 项目概述

CoCo 是基于 AgentScope 构建的自托管个人 AI 助手。通过多种消息渠道（钉钉、飞书、QQ、Discord、iMessage、Telegram、微信等）与用户交互，支持定时任务，并通过基于 Markdown 的 Skill 系统扩展能力。后端 Python (FastAPI) + 前端 React (Vite/TypeScript/Ant Design)。

## 构建与开发命令

### 从源码安装
```bash
# 先构建前端（Web UI 必需）
cd console && npm ci && npm run build
cd ..

# 将前端构建产物复制到包目录
mkdir -p src/coco/console
cp -R console/dist/. src/coco/console/

# 安装（含开发依赖）
pip install -e ".[dev,full]"
```

### 运行
```bash
coco init --defaults    # 初始化工作区
coco app                # 启动 FastAPI 服务 (http://127.0.0.1:8088/)
```

### 测试
```bash
pytest                              # 运行全部测试
pytest tests/unit/                  # 仅单元测试
pytest tests/integrated/            # 仅集成测试
pytest tests/unit/providers/        # 指定目录
pytest -m "not slow"                # 跳过慢测试
pytest tests/unit/app/test_foo.py   # 单个测试文件
```

### 代码检查与格式化
```bash
pre-commit install                   # 安装 git hooks
pre-commit run --all-files           # 运行所有检查
pip install -e ".[dev,full]" && pre-commit run --all-files  # 完整安装 + 检查
```

pre-commit 包含：black (line-length=79)、flake8、mypy、pylint、prettier (TS 文件)。如果 pre-commit 修改了文件，提交修改后重新运行直到通过。

### 前端 (console)
```bash
cd console
npm ci                # 安装依赖
npm run build         # 生产构建
npm run format        # prettier 格式化
```

### 文档站 (website)
```bash
cd website
npm run format        # 格式化文档站
```

## 代码风格

- **Python**：black 格式化，行宽 79 字符。flake8 配置 `ignore = F401,F403,W503,E731`，`extend-ignore=E203`。优先使用双引号。
- **TypeScript**：pre-commit hook 中运行 prettier 格式化。
- **提交信息**：Conventional Commits — `<type>(<scope>): <subject>`（类型：feat, fix, docs, style, refactor, perf, test, chore）。
- **PR 标题**：与提交信息格式相同，scope 必须小写。

## 架构

### 请求处理流程
```
客户端 → AuthMiddleware（提取 JWT）→ PermissionMiddleware（RBAC）→ AgentContextMiddleware（Agent 路由）→ Router → Runner → Agent
```

### 后端 (`src/coco/`)

| 模块 | 职责 |
|------|------|
| `app/_app.py` | FastAPI 应用工厂，中间件栈，生命周期初始化 |
| `app/multi_agent_manager.py` | 管理多个 Workspace 实例（懒加载，异步安全） |
| `app/workspace/` | `Workspace` = 一个完整的 Agent 运行时（runner, channels, memory, MCP, cron） |
| `app/channels/` | 渠道抽象（`BaseChannel`）+ 15 个内置渠道 + 从 `CUSTOM_CHANNELS_DIR` 加载自定义渠道 |
| `app/runner/` | `AgentRunner` 处理请求、管理会话、工具守卫审批、命令分发 |
| `app/routers/` | 20+ 个 FastAPI 路由；`agent_scoped.py` 将路由包装到 `/api/agents/{agentId}/...` |
| `app/auth.py` | JWT 认证中间件，HMAC-SHA256 令牌，bcrypt 密码 |
| `app/permissions.py` | 自动发现路由的 RBAC 中间件（路由上无需装饰器） |
| `app/ownership.py` | 数据隔离 — `get_caller_identity()`、`filter_by_user()`、`require_user_access()` |
| `app/crons/` | 基于 APScheduler 的定时任务 + 心跳 |
| `app/mcp/` | MCP 客户端管理，支持热重载监控 |
| `agents/react_agent.py` | `CoCoAgent` — 主 Agent（ReActAgent + ToolGuardMixin） |
| `agents/skills_manager.py` | Skill 生命周期管理（同步、安装、扫描、冲突解决） |
| `agents/skills_hub.py` | 远程 Skill Hub 客户端 |
| `agents/tools/` | 内置工具（browser_control, file_io, shell, memory_search 等） |
| `agents/skills/` | 内置 Skill 目录（每个含 SKILL.md + 可选 scripts/references） |
| `agents/memory/` | 记忆后端（ReMe Light），Agent Markdown 文件管理 |
| `providers/` | 模型供应商管理（OpenAI, Anthropic, Gemini, Ollama, DashScope 等） |
| `security/` | 三个子系统：secret_store（加密）、tool_guard（预执行拦截）、skill_scanner（静态分析） |
| `config/` | Pydantic 配置模型 + 工作区目录管理 |
| `db/` | SQLAlchemy/SQLite：User, UserSession, Permission, RolePermission, UserChannelOverride, AuditLog |
| `cli/` | 基于 Click 的 CLI，子命令懒加载 |
| `plugins/` | 插件系统（自定义供应商、控制命令、启动/关闭钩子） |

### Agent 上下文传播
Agent ID 通过 `AgentContextMiddleware` 设置的 `ContextVar` 传播。中间件从 URL 路径 `/api/agents/{agentId}/...` 或 `X-Agent-Id` 请求头提取并设置到 `request.state.agent_id`。后续 `get_agent_for_request()` 的优先级为：显式参数 > `request.state.agent_id`（由中间件设置）> `X-Agent-Id` 请求头 > 配置中的活跃 Agent。所有按 Agent 划分的组件（渠道、记忆、MCP、定时任务）都作用于当前 Agent 上下文。

### 渠道系统
所有渠道继承 `BaseChannel`，将原生消息转换为带 `content_parts`（TextContent, ImageContent, FileContent）的 `AgentRequest`。`ChannelManager` 持有队列并分发消息。自定义渠道从工作区 `custom_channels/` 目录自动发现。

### Skill 系统
Skill 以 Markdown 优先：一个带 YAML front matter（name, description, metadata）的 `SKILL.md` + 可选的 `scripts/` 和 `references/` 子目录。内置 Skill 位于 `src/coco/agents/skills/<skill_name>/`，激活的 Skill 位于工作区的 `skills/` 目录。无需注册——在目录中放入有效的 SKILL.md 即可生效。安装前会运行安全扫描。

### 安全
- **Tool Guard**：三层预执行拦截 — deny（阻止）、guard（记录+继续）、approve（需用户确认）。通过 Agent 上的 `ToolGuardMixin` 实现。
- **Skill Scanner**：基于 YAML 签名规则的静态分析（命令注入、提示注入、数据泄露、硬编码密钥等）。
- **Secret Store**：对磁盘上的敏感字段透明 AES 加密，主密钥来自 OS 密钥链。

### 认证与 RBAC
基于 OIDC 的 SSO + 本地 JWT 令牌。两个角色：`admin`（完全访问）和 `user`（受限访问）。`PermissionMiddleware` 自动发现路由并执行 RBAC — 写操作默认需要 admin，读操作默认需要 user。路由处理函数上无需装饰器。用户 ID 由服务端从 JWT 提取（客户端不可伪造）。

### 前端 (`console/src/`)
React 18 + TypeScript + Vite + Ant Design + i18next。页面懒加载并带重试机制。`AdminRoute` 组件守卫管理页面。`Sidebar` 按角色过滤菜单项。API 客户端在 `api/modules/` 中按领域分文件。

### 前端路由
- 用户可访问：`/chat`、`/sessions`、`/channels`、`/cron-jobs`
- 仅管理员：`/heartbeat`、`/skills`、`/skill-pool`、`/tools`、`/mcp`、`/workspace`、`/agents`、`/models`、`/environments`、`/agent-config`、`/security`、`/token-usage`、`/voice-transcription`

### 数据隔离
所有资源（Chat, CronJob 等）使用 `user_id` 字段。Console 渠道的 user_id 来自 JWT `sub`；其他渠道来自发送者 ID。admin 可查看所有数据；非 admin 仅可查看自己的数据。

## 核心模式

- **每 Agent 一个 Workspace**：每个 Agent 是完全独立的运行时，拥有自己的 runner、渠道、记忆、MCP 客户端和定时任务管理器。`MultiAgentManager` 提供懒加载、线程安全的访问。
- **热重载**：Agent 配置监控和 MCP 配置监控支持不重启热重载。
- **环境变量驱动配置**：大部分设置使用 `COCO_*` 环境变量，持久化在 `.env` 文件和 `config.json` 中。密钥通过 `secret_store` 加密存储。
- **插件系统**：插件通过自定义供应商、控制命令和生命周期钩子扩展 CoCo。从用户插件目录加载并进行 manifest 校验。

## 测试结构

- `tests/unit/` — 按模块组织的单元测试（agents/tools, app, channels, cli, local_models, providers, routers, security, utils, workspace）
- `tests/integrated/` — 集成测试（应用启动、版本检查）
- 根目录也有测试文件（`simple_test.py`、`test_improvements.py`、`test_keycloak_config.py`）
- pytest 配置 `asyncio_mode = "auto"` 和 `asyncio_default_fixture_loop_scope = "function"`
