# AllYend 项目详细分析（全量版）

更新时间：2026-01-16 23:59:10  
项目路径：`D:\1tmp\codetets`  
分析方式：静态阅读仓库代码/配置/文档（未启动服务、不连接外部网络）

> 说明：
> - 本报告尽量覆盖“做什么、为什么、怎么做、怎么部署、关键模块/数据模型/接口、风险与改进建议”。
> - 为避免泄露敏感信息，`.env` 等真实密钥/口令不做展开；环境变量以 `.env.example`/`frontend/.env.example` 为准。

---

## 0. 一句话结论

这是一个面向“爬虫/Agent/脚本任务”的一体化平台：后端用 FastAPI + SQLAlchemy 统一承载**账号/分组**、**API Key**、**爬虫接入与监控**（心跳/日志/远程指令/统计/告警）、**文件中转**（令牌上传/权限/审计）以及一个轻量**配置中心**；前端是 Next.js 14 的控制台 UI，且内置了“`/admin` 假后台诱捕 + `/hjxgl` 真后台”的安全策略。

---

## 1. 仓库结构与多工程划分

本仓库是“多工程同仓”结构（至少三块）：

1) **后端（FastAPI）**：`app/`（核心业务、数据库、路由、模板、静态资源、脚本）
2) **前端（Next.js 14）**：`frontend/`（App Router、React Query、Tailwind、shadcn/ui、测试）
3) **诱捕/演示（Node.js Express）**：根目录 `src/server.js` + `views/` + `public/`（独立运行；默认不在 docker-compose 中编排）

建议把它理解成：
- 线上推荐形态：`docker-compose.yaml` 启动 **backend + frontend + nginx 统一入口**
- 研究/演示形态：额外可单独启动根目录 Node 诱捕服务（与主系统解耦）

---

## 2. 目录树（核心文件节选）

```
.
├─ app/                         # FastAPI 后端（核心）
│  ├─ main.py                   # 应用入口：路由挂载、生命周期、日志、迁移
│  ├─ config.py                 # pydantic-settings 加载 .env（UTF-8）
│  ├─ database.py               # SQLAlchemy 引擎/Session、默认数据自举、旧库兼容升级
│  ├─ models.py                 # ORM 模型（用户/Key/爬虫/日志/指令/文件/配置/审计…）
│  ├─ schemas.py                # Pydantic schemas（对外 API 类型）
│  ├─ routers/                  # auth/crawlers/files/dashboard/admin/configs/md
│  ├─ templates/                # Jinja2 模板（部分页面/公开页）
│  ├─ static/                   # 后端静态资源（CSS/JS）
│  └─ utils/                    # IP 解析/白名单、审计工具、时间工具
├─ frontend/                    # Next.js 14 前端
│  ├─ src/app/                  # App Router（/login /dashboard /hjxgl /admin …）
│  ├─ src/lib/api/              # apiClient + endpoints + types
│  ├─ src/features/             # 业务功能模块（auth/crawlers/files/admin/honeypot…）
│  ├─ next.config.mjs           # 开发环境 rewrites（代理后端）
│  ├─ package.json              # 前端依赖与脚本（pnpm）
│  └─ Dockerfile                # 前端容器构建
├─ sdk/
│  └─ crawler_client.py         # Python SDK（同步/异步）
├─ deploy/nginx/default.conf    # Nginx 统一入口反代配置
├─ migrations/                  # Alembic 迁移脚本
├─ scripts/                     # prestart、reset_database 等脚本
├─ docker-compose.yaml          # backend + frontend + reverse-proxy
├─ Dockerfile.backend           # 后端容器构建（uv + Alembic）
├─ pyproject.toml               # Python 依赖（uv.lock 锁定）
├─ uv.lock
├─ package.json                 # 根目录 Node 诱捕服务（Express）依赖
└─ src/server.js                # 根目录 Node 诱捕服务入口
```

---

## 3. 技术栈与关键依赖

### 3.1 后端（Python）

- Python：`>=3.10`（容器用 `python:3.12-slim`）
- Web：FastAPI、Uvicorn
- ORM：SQLAlchemy 2.x
- 配置：pydantic-settings（从 `.env` 读取，显式 `env_file_encoding="utf-8"`）
- 安全：passlib[bcrypt]、python-jose[cryptography]
- 迁移：Alembic
- 其他：Jinja2、python-multipart（文件上传）、requests/httpx（对外请求/SDK）

依赖声明见：`pyproject.toml`、`uv.lock`。

### 3.2 前端（Node/TS）

- Node：`>=22`（`frontend/package.json` engines）
- 框架：Next.js 14（App Router）+ React 18.3 + TypeScript
- UI：Tailwind CSS + shadcn/ui + Radix UI
- 数据与状态：React Query、Zustand、React Hook Form + Zod
- 测试：Vitest、Playwright

依赖锁定见：`frontend/pnpm-lock.yaml`。

### 3.3 Nginx / Docker

- Docker Compose：`docker-compose.yaml` 统一编排
- Nginx：`deploy/nginx/default.conf`（路径分发、真实 IP 透传）

---

## 4. 运行与部署方式（按推荐优先级）

### 4.1 Docker Compose 一键启动（推荐）

参考：`README.md`、`docker-compose.yaml`。

核心逻辑：
- `backend`：镜像 `allyend/backend`，启动前执行 `python scripts/prestart.py`（等待 DB + Alembic upgrade），再启动 `uvicorn app.main:get_app`
- `frontend`：镜像 `allyend/frontend`，Next build 后 next start
- `reverse-proxy`：nginx 监听 `DOCKER_PROXY_PORT`（默认 8080），将 `/` 交给前端、部分路径交给后端

注意：
- 宿主机卷挂载：`./data`（数据库与文件）、`./logs`（日志）

### 4.2 本地开发（后端）

参考：`README.md`、`pyproject.toml`。

- 安装依赖（使用 uv 锁文件）：`uv sync`
- 启动：`uvicorn app.main:get_app --reload --host 0.0.0.0 --port 9093`
- 健康检查：`GET /health`

### 4.3 本地开发（前端）

参考：`frontend/README.md`。

- `cd frontend && pnpm install && pnpm dev`
- `frontend/next.config.mjs` 提供 rewrites：把 `/api`、`/pa`、`/files`、`/static`、`/pz`、`/md` 代理到后端（开发用）

### 4.4 根目录 Node 诱捕服务（可选/独立）

- 入口：`src/server.js`
- 运行：`pnpm install`（根目录）后 `pnpm start`
- 默认会在 `data/honeypot.db` 写入诱捕日志

该服务与主系统的 docker-compose 默认无集成，属于可选组件。

---

## 5. 网关路由与“/api 入口”的实际含义（非常关键）

### 5.1 Nginx 路由分发

`deploy/nginx/default.conf` 里定义的核心行为：

- `/` → 前端（Next.js）
- `/pa/`、`/files/`、`/static/` → 后端（FastAPI）
- `/api/` → 后端（FastAPI），但 **proxy_pass 末尾带 `/`**，会把外层 `/api/` 前缀剥离

这会导致一个非常重要的现象：

- 浏览器请求：`/api/files/me`
- Nginx 转发到后端时，路径变成：`/files/me`

因此，本项目实际上支持两套访问方式：

1) **直接后端路径（给 SDK/公开页/直连使用）**：`/pa/...`、`/files/...`、`/api/...`（直连后端 9093 时）
2) **通过 Nginx 统一入口给前端使用的“外层 /api 前缀”**：前端把所有请求都发到 `/api/...`，由 Nginx 去掉外层 `/api/` 再转给后端真实路径

### 5.2 与前端 `NEXT_PUBLIC_API_BASE_URL` 的关系

- 根目录 `.env.example` 和 `docker-compose.yaml` 默认将 `NEXT_PUBLIC_API_BASE_URL` 设为 `/api`
- 前端 `apiClient` 会对任意 endpoint 做 `buildApiUrl(base + path)` 拼接
- 前端 endpoints 中既包含 `/api/auth/login`，也包含 `/files/me`、`/pa/api/...`、`/hjxgl/api/...`

当 `NEXT_PUBLIC_API_BASE_URL=/api` 时：
- `/files/me` → `/api/files/me`（Nginx 去掉外层 `/api/`，后端收到 `/files/me`）
- `/api/auth/login` → `/api/api/auth/login`（Nginx 去掉外层 `/api/`，后端收到 `/api/auth/login`）

这解释了为什么 endpoints 本身带 `/api` 前缀也能工作：它依赖 Nginx 的“剥离外层 /api”行为。

建议在团队内把它明确命名为：
- **外层 API Base**：给前端调用的统一前缀（默认 `/api`）
- **后端真实路径**：FastAPI 实际路由（`/api/*`、`/files/*`、`/pa/*`、`/hjxgl/*` …）

### 5.3 开发环境 vs 生产环境：Next rewrites 与 Nginx “前缀剥离”的差异

这个项目有两种常见的“前端访问后端”方式，对应不同的 `NEXT_PUBLIC_API_BASE_URL`：

1) 生产（docker-compose + Nginx 统一入口，推荐）
- `NEXT_PUBLIC_API_BASE_URL=/api`（默认）
- Nginx 会把外层 `/api/` 剥离再转发到后端，因此前端 endpoints 可以同时存在 `/api/*` 与 `/files/*`、`/pa/*`、`/hjxgl/*` 等“真实路径”。

2) 本地开发（Next dev + 直连后端）
- 建议按 `frontend/.env.example`：`NEXT_PUBLIC_API_BASE_URL=http://localhost:9093`
- 原因：本地 `frontend/next.config.mjs` 的 rewrites 是“`/api` → 后端 `/api`”（不剥离），如果仍使用 `/api` 作为 base 且 endpoints 自身又带 `/api/...`，会出现 `/api/api/...` 的双前缀并导致 404。

额外注意：
- 管理端 API 在前端 endpoints 中是 `/hjxgl/api/*`；在生产形态下通常通过外层 base 拼成 `/api/hjxgl/api/*`，再由 Nginx 剥离外层 `/api/` 进入后端真实路径 `/hjxgl/api/*`。
- 若直接请求 `/hjxgl/api/*`，是否能命中后端取决于 Nginx 的 `/hjxgl/api/` location 配置（当前配置同样会剥离前缀，因此建议统一走 `/api/hjxgl/api/*`）。

---

## 6. 后端（FastAPI）详细拆解

### 6.1 应用入口与生命周期（`app/main.py`）

核心职责：

- 启动时区：读取 `TIMEZONE`，尽力调用 `time.tzset()`（不支持则静默降级）
- 统一日志：
  - `logs/allyend.log` 按“本地午夜”切割（`TimedRotatingFileHandler`），默认保留 14 天
  - 将 `uvicorn.access` 的输出统一传播到 root，避免重复 handler
  - 额外提供 `_AccessLogASGI`：当 `APP_ACCESS_LOG=true` 且 uvicorn 未开启 access-log 时兜底记录访问日志
- lifespan 启动过程：
  - pytest 环境跳过迁移与自举，避免污染
  - 默认只跑 Alembic（`USE_ALEMBIC_ONLY=true`）：`alembic upgrade head`，必要时做保守 stamp 兜底
  - `bootstrap_defaults()` 写入默认用户组/邀请码/超级管理员
- 中间件：
  - `ProxyHeadersMiddleware`（解析 X-Forwarded-*；信任地址来自 `FORWARDED_TRUSTED_IPS`）
  - `CORSMiddleware`（`FRONTEND_ORIGINS`，允许 credentials）
- 静态挂载：
  - `/static` → `app/static`
  - `/avatars` → `${FILE_STORAGE_DIR}/avatars`（启动时创建目录）
- 路由挂载：auth/crawlers/files/admin/dashboard/md/configs + `GET /health`

### 6.2 配置系统（`app/config.py`）

- 使用 `pydantic-settings`，从根目录 `.env` 读取（显式 `env_file_encoding="utf-8"`）
- 关键配置：
  - 安全：`SECRET_KEY`、`COOKIE_*`、`FRONTEND_ORIGINS`、`FORWARDED_TRUSTED_IPS`
  - 数据库：`DATABASE_URL`（默认 SQLite）
  - 功能策略：注册模式、日志限流/配额、是否仅 Alembic 管理
  - 文件：`FILE_STORAGE_DIR`、`LOG_DIR`
  - 告警：`SMTP_*`、`ALERT_*`

### 6.3 数据库与迁移（`app/database.py` / `scripts/prestart.py` / `migrations/`）

- ORM 基类：`database.Base`（DeclarativeBase）
- 引擎：根据 `DATABASE_URL` 创建；SQLite 额外 `check_same_thread=False`
- 迁移策略：
  - 容器启动前：`scripts/prestart.py` 等待数据库并执行 `alembic upgrade head`
  - 应用启动（lifespan）：再次执行 upgrade，并在“可确认是历史库/版本链缺失”时执行 stamp head（避免阻断启动）
- 默认数据自举：`bootstrap_defaults()`
  - 创建默认用户组（general/admins）
  - 创建 root 超级管理员（用户名来自 `ROOT_ADMIN_USERNAME`，口令默认用 `ROOT_ADMIN_PASSWORD`，否则退回 `SECRET_KEY`）
  - 创建默认邀请码等

### 6.4 数据模型（`app/models.py`）

主要表与含义（按业务域分组）：

1) 账号与组织
- `users`：用户、角色（user/admin/superadmin）、所属 `user_groups`、主题、头像、日志配额
- `user_groups`：用户组（是否启用 crawlers/files 功能）
- `user_sessions`：会话表（JWT payload 里的 sid 与此表联动，用于多设备会话/注销）
- `invite_codes` / `invite_usages`：邀请码与使用记录
- `system_settings`：系统级可配置项（如 registration_mode）

2) API Key 与爬虫工程
- `api_keys`：API Key（注意：key 明文存储；支持 `allowed_ips` 白名单；可公开/私有）
- `crawler_groups`：爬虫分组（属于 user，可着色/描述）
- `crawlers`：工程（local_id、name、状态、心跳、设备名、公开 slug、置顶、日志上限等）
- `crawler_runs`：运行记录（start/finish）
- `crawler_heartbeats`：心跳事件（payload、source_ip、device_name）
- `log_entries`：日志聚合（level、message…，与 crawler/api_key 关联）
- `crawler_commands`：远程指令（创建、拉取 next、ack 回执）
- `crawler_access_links`：快捷访问链接（面向分享/快速定位）

3) 配置模板与告警
- `crawler_config_templates`：配置模板（json/yaml）
- `crawler_config_assignments`：分配规则（对 crawler/api_key/group 生效）
- `crawler_alert_rules` / `crawler_alert_states` / `crawler_alert_events`：告警规则/状态机/触发事件（支持 email/webhook）

4) 文件中转与审计
- `file_api_tokens`：令牌上传（token 以 `up-` 前缀；支持 IP/CIDR 白名单）
- `file_entries`：文件元数据（storage_path、原始名、可见性 private/group/public/disabled、checksum、download_count）
- `file_access_logs`：文件访问审计（下载/上传等）

5) 轻量配置中心
- `app_configs`：按 app 存 JSON 配置（version、enabled、pinned）
- `app_config_read_logs`：公开读取 `/pz` 的访问日志

6) 全局操作审计
- `operation_audit_logs`：记录关键操作 before/after（刻意不落 API Key 明文）

### 6.5 鉴权与权限模型

- 登录态：Cookie `access_token`（JWT），并可带 `sid`（会话 ID）
- 用户态鉴权：`dependencies.get_current_user()`
  - 从 Cookie 取 token
  - 校验 JWT
  - 若带 sid：查 `user_sessions`，校验 revoked/过期，并刷新 last_active_at 与 ip
- 角色：`ROLE_USER / ROLE_ADMIN / ROLE_SUPERADMIN`
- 功能开关：普通用户还要受 `user.group.enable_crawlers/enable_files` 约束
- API Key：爬虫侧访问使用请求头 `X-API-Key`；可选 `allowed_ips` 限制来源

### 6.6 路由模块与主要端点

后端路由由 `app/main.py` 统一 include。

1) 认证与用户/Key（`app/routers/auth.py`）
- 页面：`GET/POST /login`、`GET/POST /register`、`GET /logout`
- API：
  - `POST /api/auth/login`、`POST /api/auth/register`、`POST /api/auth/logout`
  - `GET /api/users/me`（当前用户）
  - 会话：`GET /api/auth/sessions`、`DELETE /api/auth/sessions/{session_id}`
  - 头像：`POST/DELETE /api/users/me/avatar`
  - API Key：`GET/POST/PATCH/DELETE /api/keys`、`POST /api/keys/{id}/rotate`、`GET /api/public/keys`

2) 爬虫接入与监控（`app/routers/crawlers.py`）
- API 前缀：`/pa/api`（爬虫侧也用）
  - 注册：`POST /pa/api/register`（Header: X-API-Key）
  - 心跳：`POST /pa/api/{crawler_id}/heartbeat`
  - 运行：`POST /pa/api/{crawler_id}/runs/start`、`POST /pa/api/{crawler_id}/runs/{run_id}/finish`
  - 日志上报：`POST /pa/api/{crawler_id}/logs`
  - 指令：`POST /pa/api/{crawler_id}/commands/next`、`POST /pa/api/{crawler_id}/commands/{command_id}/ack`
  - 我的工程：`GET/PATCH/DELETE /pa/api/me/...`（含 runs/logs/stats/usage/commands/heartbeats）
  - 分组：`GET/POST/PATCH/DELETE /pa/api/groups`
  - 快捷链接：`GET/POST/PATCH/DELETE /pa/api/links`
  - 配置模板/分配：`/pa/api/config/templates`、`/pa/api/config/assignments`、`GET /pa/api/{id}/config`
  - 告警：`/pa/api/alerts/rules`、`GET /pa/api/alerts/events`
- 公开页前缀：`/pa`
  - `GET /pa/{slug}`（公开只读页）
  - `GET /pa/{slug}/api`（公开数据接口）
  - `GET /pa/{slug}/api/logs`、`/stats`、`/usage`

3) 文件服务（`app/routers/files.py`）
- 页面：`GET /files`（公开列表，仅 public）、`GET /files/manage`（管理页）
- API：
  - 公共：`GET /files/public`
  - 用户文件：`POST /files/me/up`、`GET /files/me`、`PATCH/DELETE /files/me/{id}`
  - 下载：`GET /files/{file_id}/download`（可选 token 下载）
  - 令牌：`POST/GET/PATCH /files/tokens`
  - 审计：`GET /files/api/logs`
  - 令牌上传：`POST /files/{token}/up`
  - 下载入口：`GET /files/{identifier}`（支持别名去重；`?download=1` 强制下载）

4) 仪表盘与主题（`app/routers/dashboard.py`）
- 页面：`/`、`/dashboard`、`/public` 等（注意：在 Nginx 形态下多数页面由前端接管）
- API：`GET /api/dashboard/overview`、`GET /api/dashboard/activity`、`GET/PATCH /api/users/me/theme`

5) 管理后台（`app/routers/admin.py`）
- 前缀：`/hjxgl`（避免与前端 `/admin` 冲突）
- 页面：`GET /hjxgl`（Jinja2 模板 admin.html）
- API：
  - 用户：`GET /hjxgl/api/users`、`PATCH /hjxgl/api/users/{id}`、`GET /hjxgl/api/users/{id}/logs/usage`
  - 用户组：`GET /hjxgl/api/groups`
  - 邀请码：`GET/POST/DELETE /hjxgl/api/invites`
  - 系统设置：`GET /hjxgl/api/settings`、`PATCH /hjxgl/api/settings/registration`

6) 配置中心（`app/routers/configs.py`）
- 公开：`GET /pz?app=xxx`（返回 JSON；并记录访问日志）
- 管理：前缀 `/api/configs`（需登录），支持 list/get/upsert/upload/delete/reads/stats

7) 通用回显（`app/routers/md.py`）
- `GET/POST /md`：回显 query/form/json，并附加时间/IP/URL（用于调试/透明代理）

### 6.7 日志、审计与治理

- 文件日志：`logs/allyend.log`（按天切割）
- 访问日志：
  - 优先使用 Uvicorn access log
  - 若未开启，`_AccessLogASGI` 在 ASGI 层兜底
- 审计：
  - `operation_audit_logs`：关键操作 before/after
  - `file_access_logs`：文件访问
  - `app_config_read_logs`：公开配置读取
- 日志治理：
  - per-crawler 上限：`crawler.log_max_lines/log_max_bytes` 或回退默认
  - per-user 总配额：`user.log_quota_bytes` 或回退默认
  - 超限时滚动裁剪：按批次删除旧日志（`LOG_TRIM_CHUNK_LINES`）
  - 查询频控：内存桶按 user_id 每秒限制（`LOG_QUERY_RATE_PER_SECOND`；多实例需替换为共享存储）

### 6.8 对外集成点

- SMTP：用于告警邮件（`SMTP_HOST/PORT/USERNAME/PASSWORD` 等）
- Webhook：告警触发时向外 POST（`ALERT_WEBHOOK_TIMEOUT` 控制超时）

### 6.9 关键环境变量与默认值（来自 `app/config.py`，字段级）

按“会影响系统行为”的优先级整理（默认值见 `app/config.py`）：

- 站点与运行：`SITE_NAME`、`TIMEZONE`、`HOST`、`PORT`、`SITE_ICP`
- JWT 与 Cookie 会话：`SECRET_KEY`、`ACCESS_TOKEN_EXPIRE_MINUTES`、`ALGORITHM`、`COOKIE_SECURE`、`COOKIE_SAMESITE`、`COOKIE_DOMAIN`、`COOKIE_PATH`
- 数据库：`DATABASE_URL`、`USE_ALEMBIC_ONLY`
- 用户与注册：`ROOT_ADMIN_USERNAME`、`ROOT_ADMIN_PASSWORD`、`ROOT_ADMIN_INVITE_CODE`、`DEFAULT_ADMIN_INVITE_CODE`、`DEFAULT_USER_INVITE_CODE`、`ALLOW_DIRECT_SIGNUP`
- 反代与 CORS：`FRONTEND_ORIGINS`、`FORWARDED_TRUSTED_IPS`、`APP_ACCESS_LOG`
- 日志治理：`LOG_QUERY_RATE_PER_SECOND`、`DEFAULT_USER_LOG_QUOTA_BYTES`、`DEFAULT_CRAWLER_LOG_MAX_LINES`、`DEFAULT_CRAWLER_LOG_MAX_BYTES`、`LOG_TRIM_CHUNK_LINES`、`STATS_CACHE_TTL_SECONDS`
- 文件：`FILE_STORAGE_DIR`、`LOG_DIR`
- 告警：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_USE_TLS`、`ALERT_EMAIL_SENDER`、`ALERT_WEBHOOK_TIMEOUT`

补充说明（容易踩坑）：
- “真实客户端 IP”依赖两层信任：
  - 应用层 `ProxyHeadersMiddleware` 的信任列表来自 `FORWARDED_TRUSTED_IPS`（`.env`）
  - 容器里 uvicorn 同时用 `--forwarded-allow-ips`（`Dockerfile.backend` 的 `FORWARDED_ALLOW_IPS`）控制解析；两者建议保持一致，否则会出现“X-Forwarded-* 被忽略/可伪造”的不一致现象。

### 6.10 认证与会话：Cookie JWT + 会话表（实现细节）

核心结论：该项目的“登录态”完全依赖 Cookie（不使用 Authorization 头）。

1) Token 与 Cookie 形态
- Cookie 名称：`access_token`
- Token：JWT（`sub`=用户ID，`exp`=过期时间，可选 `sid`=会话ID）
- Cookie 属性（可配置）：`HttpOnly`、`SameSite`、`Secure`、`Domain`、`Path`、`Max-Age`

2) 会话表 `user_sessions` 的作用
- 每次登录都会创建一条会话记录（`session_id` 即 JWT 的 `sid`）
- 用途：支持多设备会话、支持“注销/踢下线”而不需要黑名单全量 JWT
- `remember_me=true`：会话与 JWT 过期延长至 30 天（见 `app/routers/auth.py:_create_session`）

3) 鉴权依赖（`app/dependencies.py:get_current_user`）
- 仅从 Cookie 读取 token（`app/auth.py:get_token_from_request`）
- JWT 校验通过后：加载 `users`，并检查 `is_active`
- 若携带 `sid`：校验 `user_sessions.revoked/expires_at`，并刷新 `last_active_at/ip_address`（注意：这里会 `db.commit()`）

4) 主要端点的关键行为（`app/routers/auth.py`）
- `POST /api/auth/login`：校验 bcrypt 密码 → 创建会话（sid）→ 设置 Cookie
- `POST /api/auth/register`：执行注册策略（open/invite）→ 注册成功后直接创建会话并设置 Cookie
- `POST /api/auth/logout`：若 token 带 sid，则将对应会话置为 revoked；并删除 Cookie
- `GET /api/auth/sessions`：返回当前账号未 revoked 的会话列表，并标记 `current`
- `DELETE /api/auth/sessions/{session_id}`：吊销指定会话（revoked=true）
- `POST /api/users/me/avatar`：图片上传到 `${FILE_STORAGE_DIR}/avatars/{user_id}/`，并把 `avatar_url` 设置为 `/avatars/{user_id}/{filename}`（由 `app/main.py` 挂载静态目录）

### 6.11 API Key：明文 Key + IP 白名单（实现细节）

1) Key 的数据形态（`app/models.py:APIKey`）
- `key`：明文存储（`secrets.token_urlsafe(48)`），并会在 API 返回中直接下发（见 `app/schemas.py:APIKeyOut/PublicAPIKeyOut`）
- `active`：是否启用
- `allowed_ips`：逗号分隔 IP/CIDR/`*`（由 `ip_in_allowlist` 解析）
- `is_public`：是否公开展示（注意：公开接口也会返回 `key` 明文）
- 关联：可挂到 `crawler_groups`，并被爬虫项目（Crawler）引用

2) Key 管理端点（`app/routers/auth.py`）
- `GET /api/keys`：列出当前用户所有 Key（带 group 信息）
- `POST /api/keys`：创建 Key + 记录 `operation_audit_logs`（刻意不记录明文 key）
- `PATCH /api/keys/{id}`：更新启用状态/描述/白名单/分组 + 审计
- `POST /api/keys/{id}/rotate`：轮转 Key（重置 last_used_*）+ 审计
- `DELETE /api/keys/{id}`：删除 Key + 审计
- `GET /api/public/keys`：列出 `is_public && active` 的 Key（注意：schema 仍包含 `key` 明文）

3) 爬虫侧鉴权（`app/routers/crawlers.py:_require_api_key`）
- Header：`X-API-Key`
- 行为：按 `APIKey.key == x_api_key && active==true` 精确匹配；如配置 `allowed_ips` 则校验来源 IP；并更新 `last_used_at/last_used_ip`

### 6.12 文件服务：上传/下载/别名/令牌/权限（实现细节）

1) 物理存储与静态暴露
- 文件落盘根目录：`FILE_STORAGE_DIR`（默认 `data/files`），对象文件放在 `objects/` 子目录（例如 `objects/{random16}{suffix}`）
- 头像落盘：`${FILE_STORAGE_DIR}/avatars/...`，并通过 `/avatars` 静态挂载对外提供

2) 用户上传与元数据（`POST /files/me/up`）
- 请求：multipart（字段名 `file`，可选 `file_name/description/visibility`）
- 服务端：边读边写到 `objects/`，同时计算 `sha256` 与 `size_bytes`，写入 `file_entries`
- `visibility`：`private/group/public/disabled`（group 模式会将 `owner_group_id` 绑定到用户所属组）

3) 令牌上传（`POST /files/{token_value}/up`）
- token 格式：必须 `up-` 前缀；可自定义 suffix（仅允许字母/数字/下划线/短横线，且总长 ≤ 128），也可自动生成（最多重试 5 次）
- 令牌白名单：`allowed_ips` 与 `allowed_cidrs` 都用同一套 allowlist 解析逻辑（IP/CIDR/`*`）
- 写入：`file_entries.uploaded_by_token` 关联令牌；令牌会更新 `usage_count/last_used_at`

4) 下载别名与“重名去重”规则（`GET /files/{identifier}`）
- 目的：同名文件下载时保持稳定的“别名 URL”（如 `report.pdf`、`report-1.pdf`、`report-2.pdf`）
- 生成：对同一个 `original_name`，按创建顺序分配序号（0 为原名，>0 加 `-n` 后缀）
- 解析：将别名还原为 `(base_name, index)`，再按同名列表的顺序选取第 `index` 个条目；并二次校验 expected_alias 防止构造绕过
- 安全：显式拒绝包含 `/`、`\\`、`..` 的 filename，避免目录穿越

5) 权限模型（`_ensure_file_permission`）
- `public`：任何人可读
- `group`：同组可读；管理员/超管可读；owner 可读
- `private`：仅 owner 或管理员/超管可读
- `disabled`：默认不可读；仅 owner 或管理员/超管可读；通过 token 访问一律拒绝
- 额外限制：对非 public 文件访问会校验 `user.group.enable_files`（管理员/超管跳过）

6) 审计（`file_access_logs`）
- 上传/下载/删除/更新/列表都会写审计记录（`_log_action` 每次直接 `db.commit()`）

### 6.13 爬虫平台核心链路（实现细节）

该模块是系统主轴，主要为“无状态爬虫进程”提供：注册 → 心跳 → 日志 → 指令 → 配置下发 → 运行记录。

1) 注册（`POST /pa/api/register`）
- 鉴权：`X-API-Key`
- 逻辑：同一用户下按 name 唯一获取/创建爬虫；存在则复用并更新 `api_key_id/group_id`，并取消隐藏；不存在则创建并分配 `local_id`（用户内自增）

2) 心跳（`POST /pa/api/{crawler_id}/heartbeat`）
- 更新：`crawlers.last_heartbeat/last_source_ip/status/status_changed_at/heartbeat_payload/last_device_name`
- 记录：写入 `crawler_heartbeats`（payload 与 source_ip）
- 运行联动：若存在 running 的 `crawler_runs`，同步其 `last_heartbeat/source_ip`
- 告警：每次心跳都会评估告警规则（见 6.15）

3) 运行记录（`/runs/start` 与 `/runs/{id}/finish`）
- start：创建 `crawler_runs(status=running, started_at, source_ip)`
- finish：设置 `status/ended_at`

4) 日志上报（`POST /pa/api/{crawler_id}/logs`）
- 行为：写入 `log_entries`，并可同步更新 `crawlers.last_device_name`
- 治理：写入后会尝试执行“单爬虫上限”与“用户总配额”清理（异常会吞掉，不影响本次写入）

5) 远程指令（`/commands/next` 与 `/commands/{id}/ack`）
- next：每次最多下发 5 条 pending 且未过期的指令
- ack：回写 status/result/processed_at

6) 配置下发（`GET /pa/api/{crawler_id}/config`）
- 根据 crawler/api_key/group 等维度匹配有效 assignment（启用且版本最新），返回 `content/format/version/updated_at`；无配置则 `has_config=false`

### 6.14 日志查询、统计与缓存（实现细节）

1) 查询频控（内存桶）
- `/pa/api/me/logs` 与 `/pa/api/me/{crawler_id}/logs` 都会调用 `_enforce_log_rate_limit`
- 默认阈值：`LOG_QUERY_RATE_PER_SECOND=5`（每账号、1 秒滑窗）；超限返回 429
- 注意：多实例部署时该限流只在单进程内生效

2) 关键字 vs 正则筛选策略
- 关键字：数据库端 `ilike '%q%'` 过滤
- 正则：为保证结果质量，先放宽扫描范围（`scan_limit=min(max(limit*10, limit), MAX_REGEX_SCAN)`，默认上限 5000），拉取后在 Python 端 `re.compile` 再过滤
- 保护：有扫描上限与速率限制，但正则本身仍可能造成 CPU 开销（建议前端/后端都限制 q 长度与复杂度）

3) 趋势统计（/logs/stats）
- 单爬虫统计与公开链接统计都会扫描最多 20000 条（id/ts/message），再按桶聚合
- 统计结果有进程内 TTL 缓存：`STATS_CACHE_TTL_SECONDS`（默认 60 秒）

4) 配额与清理
- 单爬虫上限：`crawler.log_max_lines/log_max_bytes`（<=0 视为无限制；为空回退到系统默认）
- 用户总配额：`user.log_quota_bytes`（<=0 视为无限制；为空回退到系统默认）
- 清理策略：超限后每次删除最旧日志 `LOG_TRIM_CHUNK_LINES` 条并重新测量，循环有 guard（防止极端情况长时间循环）

### 6.15 告警系统（实现细节）

1) 规则与状态机
- `crawler_alert_rules`：规则主体（target_type/target_ids、trigger_type、阈值、连续触发次数、冷却时间、channels 等）
- `crawler_alert_states`：按 (rule,crawler) 维护连续命中次数、上次触发时间、最近字段值等
- `crawler_alert_events`：每次触发的事件记录（含 channel_results、error）

2) 触发时机
- 在心跳接口中调用 `_evaluate_alert_rules`，即“每次心跳”都会评估一次

3) 触发类型（当前实现）
- `status_offline`：当状态变为 offline 并达到 `consecutive_failures` 时触发
- `payload_threshold`：从 `heartbeat_payload` 提取嵌套字段，按 comparator（gt/ge/lt/le/eq/ne）与 threshold 判断，并支持连续命中

4) 通知通道
- email：使用 `smtplib`（可选 TLS），Sender 来自 `ALERT_EMAIL_SENDER` 或 `SMTP_USERNAME`
- webhook：`requests.post`，超时由 `ALERT_WEBHOOK_TIMEOUT` 控制
- 注意：发送逻辑为同步调用；规模变大后建议异步化（队列）

### 6.16 轻量配置中心（实现细节）

- 公开读取：`GET /pz?app=xxx`（无需登录）
  - 若 `app` 不存在或 `enabled=false`：对外统一返回 404（减少“探测存在性”信息泄露）
  - 成功读取会写 `app_config_read_logs`（失败会 rollback，不影响读取）
- 管理端：`/api/configs/*`（需登录）
  - upsert 时 `ensure_ascii=False` 保留中文；并递增 version
  - list 时的 `read_count` 是通过查询 read_logs 并 Counter 聚合得出（日志量很大时会变慢）
  - stats 会把时间窗内日志全量拉出再分桶（同样可能受日志量影响）

### 6.17 管理后台（/hjxgl，真后台）

- 访问控制：仅 `admin/superadmin` 可访问（`app/routers/admin.py:_require_admin`）
- 用户管理：启用/禁用、切换角色、调整用户组、调整日志配额
- 邀请码管理：创建/删除邀请码；邀请码支持过期时间、最大使用次数、绑定目标用户组、是否允许注册为管理员
- 注册策略：读写 `system_settings.registration_mode`（open/invite）
- 保护：root 超级管理员仅允许 superadmin 修改（避免管理员误操作）

### 6.18 数据库实体关系（补充：表级/链路级）

以业务链路为中心的关键关系（简化表示）：

- `user_groups` 1—N `users`（功能开关 enable_crawlers/enable_files 在此层控制）
- `users` 1—N `user_sessions`（Cookie JWT 的 sid 指向会话表，用于注销/踢下线）
- `users` 1—N `api_keys`（爬虫接入的 X-API-Key）
- `users` 1—N `crawlers`；`api_keys` 1—N `crawlers`（一个 Key 可绑定多个工程）
- `crawlers` 1—N `crawler_runs` / `crawler_heartbeats` / `crawler_commands` / `log_entries`
- `crawler_groups` 1—N `crawlers` 与 `api_keys`（用于 UI 管理与快捷链接 target）
- `crawler_access_links` → (crawler/api_key/group)（公开分享入口 /pa/{slug}）
- `file_api_tokens` 1—N `file_entries`（令牌上传来源追踪）；`users` 1—N `file_entries`
- `operation_audit_logs`、`file_access_logs`、`app_config_read_logs` 作为跨域审计/访问日志

字段级全清单见文档末尾的“附录：数据库表字段清单（自动生成）”。

---

## 7. 前端（Next.js）详细拆解

### 7.1 路由结构（`frontend/src/app`）

- 公共：
  - `/`（首页）
  - `/public`、`/public/[slug]`（公开空间/公开爬虫页入口）
  - `/files`（文件入口页）
  - `/docs`
- 认证：
  - `/login`、`/register`（位于 `src/app/(auth)`）
- 受保护区（位于 `src/app/(protected)`，统一由 `ProtectedLayout` 保护）：
  - `/dashboard`（概览）
  - `/dashboard/crawlers`、`/dashboard/crawlers/[crawlerId]`
  - `/dashboard/files`
  - `/configs`、`/configs/[app]`
  - `/settings`、`/settings/sessions`、`/settings/remote-config`
  - `/hjxgl`（真后台入口）
  - `/admin`（假后台入口，管理员自动跳转 `/hjxgl`）

### 7.2 鉴权策略（前端）

- `ProtectedLayout`（`frontend/src/components/layout/protected-layout.tsx`）：
  - 通过 `GET /api/users/me` 判断登录态（Cookie 会话）
  - 401 时清理本地状态并重定向 `/login?from=...`
  - 主题根据用户 profile 自动应用

### 7.3 数据访问层（前端 SDK）

- `frontend/src/lib/api/client.ts`：统一封装 fetch
  - 默认：`credentials: include`、`cache: no-store`
  - 错误统一抛 `ApiError(status, payload)`
- `frontend/src/lib/api/endpoints.ts`：集中维护后端路径
- `frontend/src/lib/api/types.ts`：类型定义（配合 React Query 使用）
- 文档：`docs/frontend-sdk.md`

### 7.4 “假后台诱捕”策略

- 前端 `/admin` 页面（`frontend/src/app/(protected)/admin/page.tsx`）：
  - 若用户是 admin/superadmin：自动跳转 `/hjxgl`
  - 否则展示一套“只读/不可用”的后台 UI（仿真数据 + 文案）

此策略与根目录 Node 诱捕服务目标一致，但实现路径不同：
- 前端诱捕：偏“UI 迷惑/权限挡板”
- Node 诱捕：偏“完整假后台 + 全操作审计 + 安全伪下载”

### 7.5 前端环境变量与 URL 拼接（实现细节）

- 环境变量入口：`frontend/src/lib/env.ts`
  - `env.apiBaseUrl` 默认回退为 `/api`（同源调用，便于 Cookie 生效）
  - `buildApiUrl(path)`：保证 path 以 `/` 开头，然后拼成 `${apiBaseUrl}${path}`
- fetch 默认行为：`credentials: "include"`（携带 Cookie）+ `cache: "no-store"`（避免缓存导致状态错乱）
- 本地开发建议：用 `frontend/.env.example` 将 `NEXT_PUBLIC_API_BASE_URL` 设为 `http://localhost:9093`，避免“base=/api + path=/api/... → /api/api/... 双前缀”

### 7.6 React Query 策略（轮询/缓存/失效）

以 `frontend/src/features/crawlers/queries.ts` 为例：
- QueryKey 采用分层命名（如 `["crawlers","list",filters]`、`["crawlers",id,"logs",limit,q,regex]`），便于按域失效
- 轮询：爬虫列表/详情/日志/心跳等会设置 `refetchInterval`（8s~60s），保证控制台近实时
- `placeholderData(prev)=>prev`：列表切换过滤条件时保留上一帧，降低 UI 抖动（React Query v5 推荐写法）
- Mutation 成功后会 `invalidateQueries`：例如 Key 创建/轮转会失效 `["crawlers"]` 与 `["apiKeys"]`，确保 UI 一致

### 7.7 JSON 与 FormData 的“请求体差异”（对齐后端）

前端在以下场景会刻意使用 FormData：
- 文件上传：`POST /files/me/up`（multipart，字段名 `file`）
- 文件令牌更新：`PATCH /files/tokens/{id}`（后端用 `Form(...)` 接参，所以前端用 FormData）
- 配置上传：`POST /api/configs/{app}/upload`（上传 JSON 文件）

其余大多数写接口使用 JSON（例如登录、创建 Key、创建告警规则、更新爬虫等）。

### 7.8 “真后台/假后台”在前端的落地方式

- `/hjxgl`：受保护路由中的“真后台入口”（管理员可用；实际数据来自后端 `/hjxgl/api/*`）
- `/admin`：受保护路由中的“假后台入口”
  - 若用户 role 是 admin/superadmin：自动跳转 `/hjxgl`
  - 否则展示“不可用但像真的”后台界面（诱捕/迷惑）

---

## 8. Python SDK（`sdk/crawler_client.py`）

提供两套客户端：

1) `CrawlerClient`（同步）
- 基于 requests
- 支持连接池 + 可选 retry
- 支持后台发送队列：log/heartbeat 可默认非阻塞
- 支持后台心跳线程、后台指令轮询

2) `AsyncCrawlerClient`（异步）
- 基于 httpx（可选依赖存在时启用）
- 用 asyncio 任务实现心跳/轮询，避免阻塞

共同点：
- 鉴权：请求头 `X-API-Key`
- 面向的核心端点：`/pa/api/register`、`/heartbeat`、`/runs/start`、`/logs`、`/commands/next`、`/commands/{id}/ack`

---

## 9. 根目录 Node.js 诱捕服务（独立组件）

- 入口：`src/server.js`
- 框架：Express + EJS + better-sqlite3 + express-session
- 行为：
  - 非管理员访问 `/admin`：进入假后台，所有交互写入 SQLite（`data/honeypot.db`）
  - 管理员登录后：可查看诱捕日志、导出、以及“伪下载/伪构建”等演示功能
  - `SAFE_DECOY_DOWNLOAD=true` 默认启用“安全伪下载”，避免真实压缩炸弹危害

该服务不在 `docker-compose.yaml` 中启动；如要纳入统一入口，需要额外编排/反代策略。

---

## 10. 测试、规范与工程化

### 10.1 后端测试

- `test/test_auth_api.py`：验证 Cookie 会话的登录/鉴权流程（内存 SQLite + 覆盖依赖注入）
- `test/test_files_router_utils.py`：验证文件别名去重、令牌生成等内部工具函数

依赖在 `pyproject.toml` 的 `optional-dependencies.test`。

### 10.2 前端测试

- `frontend` 提供：Vitest（单元/组件）、Playwright（E2E）配置文件
- Husky + lint-staged：提交前自动 lint/format

---

## 11. 风险点与改进建议（按优先级）

1) 路由/代理认知成本高（但可控）
- 现状：生产依赖 Nginx 对外层 `/api/` 的“前缀剥离”来适配前端 `NEXT_PUBLIC_API_BASE_URL=/api`。
- 建议：
  - 在 README 明确“外层 API Base”概念，并给出 2~3 个具体例子（/files、/api/auth、/hjxgl/api）。
  - 若要降低复杂度：考虑把后端所有路由统一挂到 `/` 下（不再有后端内部 `/api` 前缀），或修改 Nginx 不剥离前缀并调整前端 endpoints（两者择一，避免双层前缀）。

2) 安全：API Key 明文存储
- `models.APIKey.key` 目前明文；注释也提示“生产建议哈希”。
- 建议：
  - 存储哈希（例如 sha256 + salt 或 HMAC），仅在创建/轮转时展示一次明文；数据库只存 hash。

3) 多实例/水平扩展限制
- 日志查询频控、统计缓存等在内存中实现（单进程有效，多实例会失效/不一致）。
- 建议：
  - 引入 Redis（rate limit、cache、分布式锁）或把限流移动到网关层（Nginx limit_req）。

4) 告警通道的可靠性与隔离
- SMTP/Webhook 发送目前是同步调用（在请求链路或事件处理链路内）。
- 建议：
  - 规模变大后改为异步任务队列（RQ/Celery/Arq），避免阻塞主请求。

5) SQLite 与大日志量的性能瓶颈
- 日志表会快速膨胀；一些统计使用 `count`/`sum(length(...))`，在 SQLite 上可能变慢。
- 建议：
  - 生产优先 PostgreSQL；对 log_entries 建合理索引（crawler_id、created_at、level_code）。

6) 前端依赖版本一致性
- `frontend/package.json` 中 `next` 是 14，但 `eslint-config-next` 是 15（存在潜在兼容风险）。
- 建议：
  - 对齐 major 版本，避免 lint 规则与 Next 行为不一致。

7) 安全：公开接口返回 API Key 明文
- `GET /api/public/keys` 的 schema（`PublicAPIKeyOut`）包含 `key` 字段；相当于把可连接的 Key 公开下发。
- 建议：
  - 若确实需要“可公开接入”，建议返回短期临时 token 或仅返回 Key 的前后缀展示；不要返回完整明文。

8) 性能：鉴权路径频繁写入
- `get_current_user` 在每次请求带 sid 时会更新 `user_sessions.last_active_at/ip_address` 并 `commit`；文件审计 `_log_action` 同样每次 `commit`。
- 建议：
  - 高频路径尽量批量/异步写审计（或在同一事务内复用 commit），避免 SQLite 下写锁竞争。

9) 运维：/hjxgl/api 的直连路径易产生误解
- Nginx 同时配置了 `/api/` 与 `/hjxgl/api/` 两条路径，但它们的 `proxy_pass` 行为不同且都包含“前缀剥离”。
- 建议：
  - 文档明确“生产统一走 /api 前缀”的约定，减少误用；或调整 Nginx 让 `/hjxgl/api/*` 也能直连命中后端（不剥离）。

---

## 12. 新人上手清单（最短路径）

1) 先跑 Docker Compose：确认 `/`、`/api/*`、`/pa/*`、`/files/*` 可访问
2) 阅读 `.env.example`：理解 SECRET_KEY、ROOT_ADMIN、DATABASE_URL、COOKIE/CORS/PROXY 设置
3) 理解三条主链路：
   - 爬虫：`X-API-Key` → `/pa/api/register` → heartbeat/logs/commands
   - 文件：登录上传 + `up-` 令牌上传 + 下载审计
   - 配置：`/pz` 公开读取 + `/api/configs` 管理
4) 看前端 endpoints：`frontend/src/lib/api/endpoints.ts` 与后端路由是否一致
5) 跑测试：后端 `pytest`；前端 `pnpm test`/`pnpm test:ui`

---

## 13. 关键文件索引（快速定位）

- 后端入口与生命周期：`app/main.py`
- 后端配置：`app/config.py`、`.env.example`
- 数据库与自举：`app/database.py`、`scripts/prestart.py`
- 数据模型：`app/models.py`
- 核心路由：`app/routers/crawlers.py`、`app/routers/files.py`、`app/routers/auth.py`
- 前端路由：`frontend/src/app/*`
- 前端 SDK：`frontend/src/lib/api/client.ts`、`frontend/src/lib/api/endpoints.ts`、`docs/frontend-sdk.md`
- Nginx：`deploy/nginx/default.conf`
- 部署编排：`docker-compose.yaml`、`Dockerfile.backend`、`frontend/Dockerfile`
- Python SDK：`sdk/crawler_client.py`
- Node 诱捕服务：`src/server.js`、`views/`、`public/`

## 14. 附录：数据库表字段清单（自动生成）

说明：本节由 `app/models.py` 的 SQLAlchemy metadata 自动生成，用于字段级核对；类型名为 `str(col.type)` 展示，可能与实际数据库方言略有差异。

### api_keys
- 主键：id
- 唯一约束：uq_api_keys_user_local_id(user_id, local_id)
- 索引：ix_api_keys_is_public(is_public); ix_api_keys_key(key); ix_api_keys_local_id(local_id)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|local_id|INTEGER|N|||
|key|VARCHAR(128)|N|||
|name|VARCHAR(64)|Y|||
|description|TEXT|Y|||
|active|BOOLEAN|N|True||
|created_at|DATETIME|N|now||
|last_used_at|DATETIME|Y|||
|last_used_ip|VARCHAR(64)|Y|||
|is_public|BOOLEAN|N|False||
|allowed_ips|TEXT|Y|||
|user_id|INTEGER|N||users.id|
|group_id|INTEGER|Y||crawler_groups.id|

### app_config_read_logs
- 主键：id
- 索引：ix_app_config_read_logs_app(app); ix_app_config_read_logs_created_at(created_at)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|app|VARCHAR(64)|N|||
|ip_address|VARCHAR(64)|Y|||
|user_agent|VARCHAR(255)|Y|||
|created_at|DATETIME|N|now||

### app_configs
- 主键：id
- 索引：ix_app_configs_app(app)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|app|VARCHAR(64)|N|||
|description|TEXT|Y|||
|content|TEXT|N|||
|version|INTEGER|N|1||
|enabled|BOOLEAN|N|True||
|pinned_at|DATETIME|Y|||
|created_at|DATETIME|N|now||
|updated_at|DATETIME|N|now||

### crawler_access_links
- 主键：id
- 唯一约束：uq_crawler_access_slug(slug)
- 索引：ix_crawler_access_links_slug(slug)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|slug|VARCHAR(64)|N|||
|target_type|VARCHAR(16)|N|||
|description|TEXT|Y|||
|is_active|BOOLEAN|N|True||
|allow_logs|BOOLEAN|N|True||
|created_at|DATETIME|N|now||
|crawler_id|INTEGER|Y||crawlers.id|
|api_key_id|INTEGER|Y||api_keys.id|
|group_id|INTEGER|Y||crawler_groups.id|
|created_by_id|INTEGER|Y||users.id|

### crawler_alert_events
- 主键：id
- 索引：ix_crawler_alert_events_triggered_at(triggered_at)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|rule_id|INTEGER|N||crawler_alert_rules.id|
|crawler_id|INTEGER|N||crawlers.id|
|user_id|INTEGER|N||users.id|
|triggered_at|DATETIME|N|now||
|status|VARCHAR(16)|N|'pending'||
|message|TEXT|Y|||
|payload|JSON|N|dict||
|channel_results|JSON|N|list||
|error|TEXT|Y|||

### crawler_alert_rules
- 主键：id
- 唯一约束：uq_crawler_alert_rule_name(user_id, name)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|name|VARCHAR(128)|N|||
|description|TEXT|Y|||
|trigger_type|VARCHAR(32)|N|||
|target_type|VARCHAR(16)|N|'all'||
|target_ids|JSON|N|list||
|payload_field|VARCHAR(128)|Y|||
|comparator|VARCHAR(8)|Y|||
|threshold|FLOAT|Y|||
|status_from|VARCHAR(16)|Y|||
|status_to|VARCHAR(16)|Y|||
|consecutive_failures|INTEGER|N|1||
|cooldown_minutes|INTEGER|N|10||
|channels|JSON|N|list||
|is_active|BOOLEAN|N|True||
|created_at|DATETIME|N|now||
|updated_at|DATETIME|N|now||
|last_triggered_at|DATETIME|Y|||
|user_id|INTEGER|N||users.id|

### crawler_alert_states
- 主键：id
- 唯一约束：uq_crawler_alert_state(rule_id, crawler_id)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|rule_id|INTEGER|N||crawler_alert_rules.id|
|crawler_id|INTEGER|N||crawlers.id|
|user_id|INTEGER|N||users.id|
|consecutive_hits|INTEGER|N|0||
|last_triggered_at|DATETIME|Y|||
|last_status|VARCHAR(16)|Y|||
|last_value|FLOAT|Y|||
|context|JSON|N|dict||
|updated_at|DATETIME|N|now||

### crawler_commands
- 主键：id

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|command|VARCHAR(32)|N|||
|payload|JSON|Y|||
|status|VARCHAR(16)|N|'pending'||
|result|JSON|Y|||
|created_at|DATETIME|N|now||
|processed_at|DATETIME|Y|||
|expires_at|DATETIME|Y|||
|crawler_id|INTEGER|N||crawlers.id|
|issued_by_id|INTEGER|Y||users.id|

### crawler_config_assignments
- 主键：id
- 唯一约束：uq_crawler_config_assignment_target(user_id, target_type, target_id)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|name|VARCHAR(128)|N|||
|description|TEXT|Y|||
|format|VARCHAR(16)|N|'json'||
|content|TEXT|N|||
|version|INTEGER|N|1||
|is_active|BOOLEAN|N|True||
|created_at|DATETIME|N|now||
|updated_at|DATETIME|N|now||
|target_type|VARCHAR(16)|N|||
|target_id|INTEGER|N|||
|template_id|INTEGER|Y||crawler_config_templates.id|
|user_id|INTEGER|N||users.id|

### crawler_config_templates
- 主键：id
- 唯一约束：uq_crawler_config_template_name(user_id, name)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|name|VARCHAR(128)|N|||
|description|TEXT|Y|||
|format|VARCHAR(16)|N|'json'||
|content|TEXT|N|||
|is_active|BOOLEAN|N|True||
|created_at|DATETIME|N|now||
|updated_at|DATETIME|N|now||
|user_id|INTEGER|N||users.id|

### crawler_groups
- 主键：id
- 唯一约束：uq_crawler_groups_user_slug(user_id, slug)
- 索引：ix_crawler_groups_slug(slug)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|name|VARCHAR(64)|N|||
|slug|VARCHAR(64)|N|||
|description|TEXT|Y|||
|color|VARCHAR(16)|Y|||
|created_at|DATETIME|N|now||
|updated_at|DATETIME|N|now||
|user_id|INTEGER|N||users.id|

### crawler_heartbeats
- 主键：id
- 索引：ix_crawler_heartbeats_created_at(created_at)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|status|VARCHAR(16)|N|||
|payload|JSON|Y|||
|source_ip|VARCHAR(64)|Y|||
|device_name|VARCHAR(128)|Y|||
|created_at|DATETIME|N|now||
|crawler_id|INTEGER|N||crawlers.id|
|api_key_id|INTEGER|N||api_keys.id|

### crawler_runs
- 主键：id

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|status|VARCHAR(32)|N|'running'||
|started_at|DATETIME|N|now||
|ended_at|DATETIME|Y|||
|last_heartbeat|DATETIME|Y|||
|source_ip|VARCHAR(64)|Y|||
|crawler_id|INTEGER|N||crawlers.id|

### crawlers
- 主键：id
- 唯一约束：(unnamed)(public_slug); uq_crawlers_user_local_id(user_id, local_id)
- 索引：ix_crawlers_api_key_id(api_key_id); ix_crawlers_is_hidden(is_hidden); ix_crawlers_is_public(is_public); ix_crawlers_local_id(local_id); ix_crawlers_name(name)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|local_id|INTEGER|N|||
|name|VARCHAR(128)|N|||
|created_at|DATETIME|N|now||
|last_heartbeat|DATETIME|Y|||
|last_source_ip|VARCHAR(64)|Y|||
|last_device_name|VARCHAR(128)|Y|||
|is_hidden|BOOLEAN|N|False||
|hidden_at|DATETIME|Y|||
|status|VARCHAR(16)|N|'offline'||
|status_changed_at|DATETIME|Y|||
|uptime_ratio|FLOAT|Y|||
|uptime_minutes|FLOAT|Y|||
|heartbeat_payload|JSON|Y|||
|is_public|BOOLEAN|N|False||
|public_slug|VARCHAR(64)|Y|||
|pinned_at|DATETIME|Y|||
|log_max_lines|INTEGER|Y|||
|log_max_bytes|INTEGER|Y|||
|user_id|INTEGER|N||users.id|
|api_key_id|INTEGER|N||api_keys.id|
|group_id|INTEGER|Y||crawler_groups.id|

### file_access_logs
- 主键：id

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|action|VARCHAR(32)|N|||
|ip_address|VARCHAR(64)|Y|||
|user_agent|VARCHAR(255)|Y|||
|status|VARCHAR(32)|N|'success'||
|created_at|DATETIME|N|now||
|file_id|INTEGER|Y||file_entries.id|
|user_id|INTEGER|Y||users.id|
|token_id|INTEGER|Y||file_api_tokens.id|

### file_api_tokens
- 主键：id
- 索引：ix_file_api_tokens_token(token)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|token|VARCHAR(128)|N|||
|name|VARCHAR(128)|Y|||
|description|TEXT|Y|||
|is_active|BOOLEAN|N|True||
|allowed_ips|TEXT|Y|||
|allowed_cidrs|TEXT|Y|||
|usage_count|INTEGER|N|0||
|last_used_at|DATETIME|Y|||
|created_at|DATETIME|N|now||
|user_id|INTEGER|N||users.id|

### file_entries
- 主键：id
- 唯一约束：(unnamed)(storage_path)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|storage_path|VARCHAR(255)|N|||
|original_name|VARCHAR(255)|N|||
|description|TEXT|Y|||
|content_type|VARCHAR(128)|Y|||
|size_bytes|INTEGER|N|||
|checksum_sha256|VARCHAR(64)|Y|||
|visibility|VARCHAR(16)|N|'private'||
|is_anonymous|BOOLEAN|N|False||
|created_at|DATETIME|N|now||
|updated_at|DATETIME|N|now||
|download_count|INTEGER|N|0||
|owner_id|INTEGER|Y||users.id|
|owner_group_id|INTEGER|Y||user_groups.id|
|uploaded_by_user_id|INTEGER|Y||users.id|
|uploaded_by_token_id|INTEGER|Y||file_api_tokens.id|

### invite_codes
- 主键：id
- 索引：ix_invite_codes_code(code)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|code|VARCHAR(64)|N|||
|note|TEXT|Y|||
|allow_admin|BOOLEAN|N|False||
|max_uses|INTEGER|Y|||
|used_count|INTEGER|N|0||
|expires_at|DATETIME|Y|||
|created_at|DATETIME|N|now||
|creator_id|INTEGER|Y||users.id|
|target_group_id|INTEGER|Y||user_groups.id|

### invite_usages
- 主键：id

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|used_at|DATETIME|N|now||
|ip_address|VARCHAR(64)|Y|||
|invite_id|INTEGER|N||invite_codes.id|
|user_id|INTEGER|N||users.id|

### log_entries
- 主键：id
- 索引：ix_log_entries_level_code(level_code)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|level|VARCHAR(16)|N|'INFO'||
|level_code|INTEGER|N|20||
|message|TEXT|N|||
|ts|DATETIME|N|now||
|source_ip|VARCHAR(64)|Y|||
|device_name|VARCHAR(128)|Y|||
|crawler_id|INTEGER|N||crawlers.id|
|run_id|INTEGER|Y||crawler_runs.id|
|api_key_id|INTEGER|Y||api_keys.id|

### operation_audit_logs
- 主键：id
- 索引：ix_operation_audit_logs_actor_id(actor_id); ix_operation_audit_logs_created_at(created_at); ix_operation_audit_logs_target_id(target_id)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|action|VARCHAR(64)|N|||
|target_type|VARCHAR(32)|N|||
|target_id|INTEGER|Y|||
|target_name|VARCHAR(128)|Y|||
|before|JSON|Y|||
|after|JSON|Y|||
|actor_id|INTEGER|Y||users.id|
|actor_name|VARCHAR(128)|Y|||
|actor_ip|VARCHAR(64)|Y|||
|created_at|DATETIME|N|now||

### system_settings
- 主键：id
- 唯一约束：(unnamed)(key)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|key|VARCHAR(128)|N|||
|value|TEXT|N|||
|updated_at|DATETIME|N|now||

### user_groups
- 主键：id
- 唯一约束：(unnamed)(name)
- 索引：ix_user_groups_slug(slug)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|name|VARCHAR(64)|N|||
|slug|VARCHAR(64)|N|||
|description|TEXT|Y|||
|is_default|BOOLEAN|N|False||
|enable_crawlers|BOOLEAN|N|True||
|enable_files|BOOLEAN|N|True||
|created_at|DATETIME|N|now||
|updated_at|DATETIME|N|now||

### user_sessions
- 主键：id
- 索引：ix_user_sessions_revoked(revoked); ix_user_sessions_session_id(session_id); ix_user_sessions_user_id(user_id)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|session_id|VARCHAR(64)|N|||
|user_agent|VARCHAR(255)|Y|||
|ip_address|VARCHAR(64)|Y|||
|remember_me|BOOLEAN|N|False||
|created_at|DATETIME|N|now||
|last_active_at|DATETIME|Y|||
|expires_at|DATETIME|Y|||
|revoked|BOOLEAN|N|False||
|user_id|INTEGER|N||users.id|

### users
- 主键：id
- 唯一约束：(unnamed)(email)
- 索引：ix_users_id(id); ix_users_username(username)

|字段|类型|可空|默认|外键|
|-|-|-|-|-|
|id|INTEGER|N|||
|username|VARCHAR(64)|N|||
|hashed_password|VARCHAR(255)|N|||
|display_name|VARCHAR(128)|Y|||
|email|VARCHAR(128)|Y|||
|avatar_url|VARCHAR(255)|Y|||
|is_active|BOOLEAN|N|True||
|log_quota_bytes|INTEGER|Y|||
|role|VARCHAR(32)|N|'user'||
|is_root_admin|BOOLEAN|N|False||
|created_at|DATETIME|N|now||
|updated_at|DATETIME|N|now||
|theme_name|VARCHAR(32)|N|'classic'||
|theme_primary|VARCHAR(16)|N|'#10b981'||
|theme_secondary|VARCHAR(16)|N|'#1f2937'||
|theme_background|VARCHAR(16)|N|'#f9fafb'||
|is_dark_mode|BOOLEAN|N|False||
|group_id|INTEGER|Y||user_groups.id|
|invited_by_id|INTEGER|Y||users.id|
|invite_code_id|INTEGER|Y||invite_codes.id|

## 15. 附录：后端路由总览（FastAPI routes 自动生成）

说明：以下为 FastAPI "真实路径"（直连后端时的路径）；若走 Nginx 统一入口且 `NEXT_PUBLIC_API_BASE_URL=/api`，则会再叠加一层外层 `/api` 前缀并由网关剥离。

|方法|路径|endpoint|
|-|-|-|
|GET|/|home|
|POST|/api/auth/login|api_login|
|POST|/api/auth/logout|api_logout|
|POST|/api/auth/register|api_register|
|GET|/api/auth/sessions|list_sessions|
|DELETE|/api/auth/sessions/{session_id}|revoke_session|
|GET|/api/configs|list_configs|
|DELETE|/api/configs/{app}|delete_config|
|GET|/api/configs/{app}|get_config|
|PUT|/api/configs/{app}|upsert_config|
|PATCH|/api/configs/{app}/meta|update_meta|
|GET|/api/configs/{app}/reads|list_reads|
|GET|/api/configs/{app}/stats|stats|
|POST|/api/configs/{app}/upload|upload_config|
|GET|/api/dashboard/activity|get_dashboard_activity|
|GET|/api/dashboard/overview|get_dashboard_overview|
|GET|/api/keys|list_keys|
|POST|/api/keys|create_key|
|DELETE|/api/keys/{key_id}|delete_key|
|PATCH|/api/keys/{key_id}|update_key|
|POST|/api/keys/{key_id}/rotate|rotate_key|
|GET|/api/public/keys|list_public_keys|
|GET|/api/users/me|api_current_user|
|DELETE|/api/users/me/avatar|delete_avatar|
|POST|/api/users/me/avatar|upload_avatar|
|GET|/api/users/me/theme|get_my_theme|
|PATCH|/api/users/me/theme|update_my_theme|
|GET|/dashboard|dashboard|
|GET|/dashboard/crawlers|crawlers_page|
|GET|/dashboard/crawlers/{crawler_id}|crawler_detail_page|
|GET|/files|files_list|
|GET|/files/api/logs|list_access_logs|
|GET|/files/manage|files_manage|
|GET|/files/me|list_my_files|
|POST|/files/me/up|user_upload|
|DELETE|/files/me/{file_id}|delete_my_file|
|PATCH|/files/me/{file_id}|update_my_file|
|GET|/files/public|list_public_files|
|GET|/files/tokens|list_file_tokens|
|POST|/files/tokens|create_file_token|
|PATCH|/files/tokens/{token_id}|update_file_token|
|GET|/files/{file_id}/download|download_file|
|GET|/files/{identifier}|files_entry|
|POST|/files/{token_value}/up|token_upload|
|GET|/health|healthcheck|
|GET|/hjxgl|admin_console|
|GET|/hjxgl/|admin_console|
|GET|/hjxgl/api/groups|admin_list_groups|
|GET|/hjxgl/api/invites|admin_list_invites|
|POST|/hjxgl/api/invites|admin_create_invite|
|DELETE|/hjxgl/api/invites/{invite_id}|admin_delete_invite|
|GET|/hjxgl/api/settings|admin_get_settings|
|PATCH|/hjxgl/api/settings/registration|admin_update_registration|
|GET|/hjxgl/api/users|admin_list_users|
|PATCH|/hjxgl/api/users/{user_id}|admin_update_user|
|GET|/hjxgl/api/users/{user_id}/logs/usage|admin_user_log_usage|
|GET|/login|login_page|
|POST|/login|login_form|
|GET|/logout|logout|
|GET,POST|/md|md|
|GET|/pa/api/alerts/events|list_alert_events|
|GET|/pa/api/alerts/rules|list_alert_rules|
|POST|/pa/api/alerts/rules|create_alert_rule|
|DELETE|/pa/api/alerts/rules/{rule_id}|delete_alert_rule|
|PATCH|/pa/api/alerts/rules/{rule_id}|update_alert_rule|
|GET|/pa/api/config/assignments|list_config_assignments|
|POST|/pa/api/config/assignments|create_config_assignment|
|DELETE|/pa/api/config/assignments/{assignment_id}|delete_config_assignment|
|PATCH|/pa/api/config/assignments/{assignment_id}|update_config_assignment|
|GET|/pa/api/config/templates|list_config_templates|
|POST|/pa/api/config/templates|create_config_template|
|DELETE|/pa/api/config/templates/{template_id}|delete_config_template|
|PATCH|/pa/api/config/templates/{template_id}|update_config_template|
|GET|/pa/api/groups|list_groups|
|POST|/pa/api/groups|create_group|
|DELETE|/pa/api/groups/{group_id}|delete_group|
|PATCH|/pa/api/groups/{group_id}|update_group|
|GET|/pa/api/links|list_quick_links|
|POST|/pa/api/links|create_quick_link|
|DELETE|/pa/api/links/{link_id}|delete_quick_link|
|PATCH|/pa/api/links/{link_id}|update_quick_link|
|GET|/pa/api/me|my_crawlers|
|GET|/pa/api/me/logs|my_logs|
|GET|/pa/api/me/logs/usage|my_logs_usage|
|DELETE|/pa/api/me/{crawler_id}|delete_my_crawler|
|GET|/pa/api/me/{crawler_id}|my_crawler_detail|
|PATCH|/pa/api/me/{crawler_id}|update_my_crawler|
|GET|/pa/api/me/{crawler_id}/commands|my_crawler_commands|
|POST|/pa/api/me/{crawler_id}/commands|create_crawler_command|
|GET|/pa/api/me/{crawler_id}/heartbeats|my_crawler_heartbeats|
|DELETE|/pa/api/me/{crawler_id}/logs|clear_my_crawler_logs|
|GET|/pa/api/me/{crawler_id}/logs|my_crawler_logs|
|GET|/pa/api/me/{crawler_id}/logs/stats|my_crawler_logs_stats|
|GET|/pa/api/me/{crawler_id}/logs/usage|my_crawler_logs_usage|
|GET|/pa/api/me/{crawler_id}/runs|my_crawler_runs|
|POST|/pa/api/register|register_crawler|
|POST|/pa/api/{crawler_id}/commands/next|fetch_commands|
|POST|/pa/api/{crawler_id}/commands/{command_id}/ack|acknowledge_command|
|GET|/pa/api/{crawler_id}/config|fetch_crawler_config|
|POST|/pa/api/{crawler_id}/heartbeat|heartbeat|
|POST|/pa/api/{crawler_id}/logs|create_log|
|POST|/pa/api/{crawler_id}/runs/start|start_run|
|POST|/pa/api/{crawler_id}/runs/{run_id}/finish|finish_run|
|GET|/pa/{slug}|public_crawler_page|
|GET|/pa/{slug}/api|public_crawler_summary_api|
|GET|/pa/{slug}/api/logs|public_logs|
|GET|/pa/{slug}/api/logs/stats|public_logs_stats|
|GET|/pa/{slug}/api/logs/usage|public_logs_usage|
|GET|/public|public_space|
|GET|/pz|fetch_public_config|
|GET|/register|register_page|
|POST|/register|register_form|
