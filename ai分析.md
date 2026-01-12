# AllYend 项目 AI 分析报告（功能与目的导向）

更新时间：2026-01-12  
分析对象：`F:\codes\allyend`（当前仓库快照）

> 本报告基于仓库内现有代码、配置与文档（尤其是 `README.md`、`app/`、`frontend/`、`sdk/`、`deploy/`、`migrations/`）进行归纳整理，目标是让你在“不了解代码细节”的情况下，也能快速理解该项目**做什么**、**为什么做**、**怎么做**、**如何部署与演进**。

---

## 1. 项目定位（它是什么、解决什么问题）

AllYend 是一个面向“爬虫/Agent/脚本类任务”的一体化平台，核心目标是把下面四类能力放到同一个系统里，并且支持账号隔离、分组治理与审计追踪：

1) **爬虫接入与监控**：注册/心跳/运行开始结束/日志上报/统计，帮助你实时知道各个爬虫“是否在线、跑到哪、输出什么”。  
2) **日志聚合与治理**：将爬虫侧日志统一入库（而非散落在机器上），并提供查询、过滤、统计与配额/清理机制，防止日志无限膨胀。  
3) **远程指令（控制面）**：从平台下发指令到爬虫端，爬虫拉取指令并回执，形成一个轻量控制通道。  
4) **文件中转/网盘**：支持登录用户上传、以及“令牌上传（up- 前缀）”，用于临时文件交换、报表落盘下载、跨环境文件中转；同时带访问审计。

此外，仓库还包含一个**独立的 Node.js 演示/研究组件**：`decoy-admin-honeypot`（“/admin 诱捕假后台 + 真后台日志面板”），用于安全研究/教学场景的诱捕与审计，它与 AllYend 主站相互独立，默认不随 Docker 编排启动（见 `README.md` 末尾说明与根目录 `package.json`）。

---

## 2. 典型使用场景（用户视角）

### 2.1 爬虫/Agent 监控场景
- 你有多台机器、多套爬虫（或定时任务），希望统一管理：
  - 哪些任务在线，多久没心跳了
  - 每次运行何时开始/结束、是否失败
  - 运行过程中输出的日志能集中检索（含等级/设备名/IP）
  - 可以临时下发“重试/停止/切换配置/清理缓存”等指令

### 2.2 文件中转场景
- 你希望爬虫跑完自动上传结果文件（Excel/PDF/zip），并给业务方一个“可控访问链接”：
  - 支持“令牌上传”：无需账号登录，只要拿到 `up-xxxxx` 令牌即可上传/列出/下载
  - 支持可见性：private/group/public/disabled
  - 支持下载重名去重（`report.pdf`、`report-1.pdf`…）
  - 支持访问审计（谁/什么 IP/何时下载了）

### 2.3 轻量“配置中心”场景
- 需要给不同 app/脚本提供远程 JSON 配置：
  - 公共读取：`GET /pz?app=xxx` 返回 JSON（无需登录，但记录访问日志）
  - 登录管理：`/api/configs/**` 支持版本号、启用/禁用、置顶、读取统计

---

## 3. 总体架构（组件与边界）

### 3.1 技术栈概览

**后端（平台核心）**
- Web 框架：FastAPI
- ORM：SQLAlchemy 2.x（Declarative + Session）
- 配置：pydantic-settings（读取 `.env`，UTF-8）
- 模板：Jinja2（后端仍提供部分页面，如 `/files`、`/pa/{slug}` 等）
- 鉴权：Cookie 内 JWT（`access_token`），配合 `user_sessions` 支持多设备会话
- 迁移：Alembic（`migrations/`）

**前端（管理控制台 / UI）**
- Next.js 14（App Router）+ React 18.3 + TypeScript
- Tailwind CSS + shadcn/ui + Radix UI
- 数据请求：封装 `fetch` + React Query
- 测试：Vitest、Playwright

**基础设施**
- 反向代理：Nginx（统一入口）
- 容器：Docker Compose（backend + frontend + reverse-proxy）
- 默认数据库：SQLite（`data/app.db`），可切换 PostgreSQL/MySQL（通过 `DATABASE_URL`）
- 文件存储：本地目录（默认 `data/files/objects`）

### 3.2 部署拓扑与路由分发

仓库推荐的生产入口是 `docker-compose.yaml` + `deploy/nginx/default.conf`：

- 用户浏览器访问：`http://<host>:8080/`
  - `/`（以及绝大多数页面路由）→ **Next.js 前端**
  - `/api/*` → **FastAPI 后端**（JSON API）
  - `/pa/*` → **FastAPI 后端**（爬虫接入 + 公开页）
  - `/files/*` → **FastAPI 后端**（文件页面 + 上传下载 + API）
  - `/static/*`、`/avatars/*` → **FastAPI 后端静态资源**
  - `/hjxgl/api/*` → **FastAPI 后端**（管理 API；页面部分由前端负责）

关键文件：
- 反代配置：`deploy/nginx/default.conf`
- 编排入口：`docker-compose.yaml`

### 3.3 核心数据流（按业务域）

1) **账号域**：用户注册/登录 → 写入用户表 → 登录创建 `user_sessions` → Cookie 写入 JWT（携带 sid）  
2) **爬虫域**：API Key → 爬虫注册（绑定/创建工程）→ 心跳/日志/运行 → 统计/告警/公开链接  
3) **文件域**：登录上传或令牌上传 → 文件对象落盘 + FileEntry 入库 → 下载/列表 → 审计落库  
4) **配置域**：管理员写入 app 配置 → 公共读取 `/pz` → 读日志与统计落库

---

## 4. 目录结构与职责划分（理解代码从哪看起）

> 这里按“你要改功能/查问题时，应该去哪找”来组织。

### 4.1 后端（`app/`）

- `app/main.py`：FastAPI 初始化、路由挂载、中间件、日志系统、启动时迁移与自举
- `app/config.py`：`.env` 配置（UTF-8）加载与类型校验
- `app/database.py`：SQLAlchemy engine/session、启动自举数据、兼容性列升级（历史库兜底）
- `app/models.py`：ORM 模型（用户/爬虫/日志/文件/配置/审计等）
- `app/schemas.py`：Pydantic Schema（请求/响应模型）
- `app/auth.py`：密码哈希 + JWT 编解码 + 从 Cookie 提取 token
- `app/dependencies.py`：依赖注入（DB session、当前用户解析与会话校验）
- `app/routers/`：按业务域拆分路由
  - `auth.py`：注册/登录/会话/头像/API Key
  - `crawlers.py`：爬虫接入/日志/指令/分组/公开页/配置下发/告警
  - `files.py`：网盘/令牌上传/下载/审计
  - `admin.py`：后台管理（`/hjxgl/api/**`）
  - `configs.py`：应用 JSON 配置（`/api/configs/**` + `/pz`）
  - `dashboard.py`：后端模板页（部分可能为“直连后端”时的备用 UI）
  - `md.py`：通用回显接口 `/md`

### 4.2 前端（`frontend/`）

- `frontend/src/app/`：Next.js App Router 页面
  - `(auth)/login`、`(auth)/register`：登录/注册
  - `(protected)/dashboard`、`(protected)/dashboard/crawlers/[crawlerId]`：控制台与爬虫详情
  - `(protected)/configs`、`(protected)/settings`、`(protected)/admin`、`(protected)/hjxgl`：配置中心、会话管理、管理入口等
- `frontend/src/lib/api/`：前端 API SDK（`fetch` 封装 + endpoints + types）
- `frontend/next.config.mjs`：开发环境 rewrites（把 `/api`、`/pa`、`/files`、`/pz` 等代理到后端）

### 4.3 Python SDK（`sdk/`）

- `sdk/crawler_client.py`：爬虫端/Agent 侧 SDK（同步 + 异步），对接 `/pa/api/**`

### 4.4 运维/部署（根目录与 `deploy/`、`migrations/`、`scripts/`）

- `docker-compose.yaml`：后端、前端、Nginx 统一入口
- `Dockerfile.backend`、`frontend/Dockerfile`：各自的镜像构建方式
- `deploy/nginx/default.conf`：反代路由/真实 IP 透传
- `migrations/`：Alembic 迁移（初始化 + 增量演进）
- `scripts/prestart.py`：容器启动前等待 DB + 自动迁移

### 4.5 独立组件：诱捕假后台（根目录 Node 项目）

- `package.json`（根目录）：`decoy-admin-honeypot` 的依赖与脚本
- `src/server.js`：Express + EJS + SQLite 的诱捕/审计逻辑
- `views/`、`public/`：诱捕 UI 模板与静态资源

---

## 5. 后端核心设计（业务能力如何落地）

### 5.1 配置系统（`.env` → `Settings`）

配置入口：`app/config.py`  
特点：
- 统一从 `.env` 读取，明确指定 `env_file_encoding="utf-8"`（避免 Windows 编码问题）
- 对关键字段做了“容错解析”
  - `FRONTEND_ORIGINS` / `FORWARDED_TRUSTED_IPS` 支持“逗号分隔字符串”或 JSON 数组
  - `COOKIE_SAMESITE` 自动归一化到 `lax/strict/none`

常见关键变量（节选，详见 `.env.example` 与 `app/config.py`）：
- 安全：`SECRET_KEY`、`COOKIE_SECURE`、`COOKIE_SAMESITE`、`COOKIE_DOMAIN`
- 数据库：`DATABASE_URL`
- 反代与跨域：`FRONTEND_ORIGINS`、`FORWARDED_TRUSTED_IPS`
- 日志治理：`LOG_QUERY_RATE_PER_SECOND`、`DEFAULT_USER_LOG_QUOTA_BYTES`、`DEFAULT_CRAWLER_LOG_MAX_*`
- 文件：`FILE_STORAGE_DIR`、`LOG_DIR`

### 5.2 鉴权与会话（Cookie JWT + Session 表）

实现位置：
- JWT 工具：`app/auth.py`
- 当前用户依赖：`app/dependencies.py`
- 登录/会话管理：`app/routers/auth.py`
- 数据表：`user_sessions`（见 `app/models.py`）

核心机制：
- 登录后服务端下发 Cookie：`access_token=<JWT>`（HttpOnly）
- JWT 的 `sub` 存用户 id；可选携带 `sid`（会话 id）
- 若 token 含 `sid`，每次请求会校验：
  - `user_sessions` 是否存在、未撤销、未过期
  - 并刷新 `last_active_at` 与 IP

优点：
- 不依赖 LocalStorage，避免前端 XSS 直接窃取 token
- 多设备会话可管理、可撤销（接口：`/api/auth/sessions`）

需要注意的点（现状观察）：
- 已优化：表单注册与 `api_register` 注册成功后会创建 `user_sessions`，
  并在 JWT 中写入 `sid`，因此注册会话也可以在会话管理列表中查看/撤销。

### 5.3 权限模型（角色 + 用户组）

角色（`app/constants.py`）：
- `user` / `admin` / `superadmin`

用户组（`user_groups`）：
- `enable_crawlers`：是否启用爬虫功能（`crawlers.py` 中明确做了 gating）
- `enable_files`：是否启用文件功能（已在 `files.py` 中做 gating，与爬虫功能保持一致）

邀请码体系（`invite_codes`、`invite_usages`）：
- 注册策略由 `system_settings.registration_mode` 控制（open/invite/closed）
- 邀请码可绑定目标用户组、可设置是否允许注册为管理员

### 5.4 爬虫接入与监控（/pa）

路由与入口：
- 爬虫端 API：`/pa/api/**`（`X-API-Key` 认证）
- 管理端 API：`/pa/api/me/**`（Cookie 登录认证）
- 公开页/公开 API：`/pa/{slug}`、`/pa/{slug}/api/**`

关键表：
- `api_keys`：API Key 管理（支持分组、启用、公开、IP 白名单）
- `crawlers`：工程（Crawler）实体，一个用户下多个工程
- `crawler_runs`：运行记录
- `log_entries`：日志
- `crawler_heartbeats`：心跳事件
- `crawler_commands`：远程指令与回执
- `crawler_groups`：爬虫分组（与 API Key、Crawler 关联）
- `crawler_access_links`：公开快捷链接（slug）
- `crawler_config_templates` / `crawler_config_assignments`：配置模板与分配（用于爬虫端拉取配置）
- `crawler_alert_rules` / `crawler_alert_states` / `crawler_alert_events`：告警规则、状态、事件

典型流程（简化）：
1) 管理端创建 API Key：`POST /api/keys`  
2) 爬虫端注册工程：`POST /pa/api/register`（Header `X-API-Key`）  
3) 心跳：`POST /pa/api/{crawler_id}/heartbeat`（可带 `device_name` 与 payload）  
4) 运行开始/结束：`/runs/start`、`/runs/{run_id}/finish`  
5) 日志上报：`POST /pa/api/{crawler_id}/logs`  
6) 指令拉取与回执：`/commands/next` → `/commands/{id}/ack`  
7) 管理端查询：`GET /pa/api/me`、`/me/{id}/logs`、`/me/{id}/commands` 等  

日志治理（非常关键）：
- **账号维度频控**：内存桶 `_LOG_RATE_BUCKETS`（每秒请求次数限制，单实例有效，多实例需外置存储）
- **配额**：
  - 单爬虫：`log_max_lines` / `log_max_bytes`（可覆盖系统默认）
  - 用户总配额：`log_quota_bytes`（可覆盖系统默认）
- 超限处理：滚动删除最旧日志（chunk 批量删除），避免库无限增长

公开页（`crawler_access_links`）：
- 可以生成 `slug` 链接，公开“只读摘要”
- 可配置 `allow_logs`：是否允许公开查看日志（默认建议关闭，避免泄露）

### 5.5 文件中转与网盘（/files）

路由入口：
- 页面：`GET /files`（公开文件列表，仅列出 `visibility=public`）  
- 页面：`GET /files/manage`（管理页，需要登录）  
- 登录用户上传：`POST /files/me/up`  
- 令牌上传：`POST /files/{token}/up`（token 必须 `up-` 前缀）  
- 下载：
  - `GET /files/{file_id}/download`（可选 query token_value）
  - `GET /files/{alias}`（别名下载，支持重名自动 `-1/-2`）
  - `GET /files/{up-token}`（不加 `download=1` 时返回该 token 所属用户的文件列表）

关键表：
- `file_api_tokens`：令牌（可启用/禁用、可配置 allowed_ips 与 allowed_cidrs）
- `file_entries`：文件元数据（对象存储路径、原始名、hash、可见性、归属人/组）
- `file_access_logs`：访问审计（upload/download/delete/list）

对象存储方式：
- 文件实际写入：`{FILE_STORAGE_DIR}/objects/<random>.<suffix>`
- 元数据里记录 `storage_path`（相对路径）
- 下载时按权限校验后 `FileResponse` 直出文件

安全要点：
- token 支持 CIDR 校验（使用 `ipaddress`），适合临时开放某网段上传/下载
- 下载别名严格做了 path traversal 防护（拒绝 `..`、`/`、`\\`）

### 5.6 应用 JSON 配置中心（/api/configs + /pz）

能力概览（`app/routers/configs.py`）：
- 公开读取：`GET /pz?app=xxx`
  - 返回 JSON
  - 记录访问日志：ip/ua/时间（表 `app_config_read_logs`）
  - 支持 enabled 开关：禁用后对外表现为 404（避免泄露存在性）
- 登录管理：`/api/configs/**`
  - 列表、详情、upsert、上传、删除
  - 元数据更新：enabled/pinned
  - 访问统计：时间序列 + Top IP

适用场景：
- 给爬虫端、前端、或其它内部服务提供“无需重部署即可修改的配置”

### 5.7 审计与可追溯性

后端做了两类审计：
1) **操作审计**：`operation_audit_logs`（见 `app/utils/audit.py`）
   - 对象：API Key、分组等关键变更
   - 特点：不写入敏感字段（例如不会记录明文 API Key）
2) **文件访问审计**：`file_access_logs`
   - 记录 upload/download/delete/list 等动作与 IP

日志文件（应用日志）：
- `app/main.py` 启动时配置 `logs/allyend.log`（按天切割，保留 14 天）
- 额外提供 ASGI 层访问日志兜底（即使 uvicorn 未开启 `--access-log`）

---

## 6. 前端实现与后端对接（前后端分离现状）

### 6.1 前端工程定位

前端目录：`frontend/`  
目标：提供“现代化、性能优先”的管理控制台 UI，默认走 Cookie 会话（不再使用 Authorization Bearer）。

核心封装：
- `frontend/src/lib/api/client.ts`：统一 fetch 封装，默认 `credentials: "include"`，错误统一抛 `ApiError`
- `frontend/src/lib/api/endpoints.ts`：所有后端端点路径集中管理
- `frontend/src/lib/api/types.ts`：前端类型定义（与后端响应结构对应）

### 6.2 开发环境代理策略

`frontend/next.config.mjs` 定义了 rewrites，把以下路径代理到后端（开发时解决跨域与 Cookie 问题）：
- `/api/*`、`/pa/*`、`/files/*`、`/pz`、`/md`、`/static/*`

这意味着：
- 开发时（`pnpm dev`）即使你在 `http://localhost:3000` 访问 `/pa/...`，也会被 Next 代理到后端 `http://localhost:9093`。

### 6.3 与 Nginx 生产反代的关系

生产建议：
- 通过 Nginx 统一入口，前端同源访问 `/api`，避免跨域与 Cookie SameSite/secure 问题。

需要注意的潜在冲突（属于“架构取舍点”）：
- Nginx 默认将 `/files/` 直接反代到后端，因此 **前端实现的 `/files` 页面在生产入口下不可达**（会被后端接管）。  
  - 这不一定是错，但需要明确：到底是“后端模板负责 files UI”，还是“前端负责 files UI”。两者长期并存会造成维护成本与路由冲突。

### 6.4 接口覆盖情况（现状观察）

从 `frontend/src/lib/api/endpoints.ts` 可以看出前端计划覆盖：
- auth / sessions / avatar
- files / tokens / logs
- crawlers / logs / runs / commands / groups / config / alerts / quick links
- dashboard / overview / recentActivity / theme
- admin（`/hjxgl/api/**`）
- configs（`/api/configs/**`）

同时也能看到“待补齐”的接口占位：
- `dashboard.overview: "/api/dashboard/overview"`
- `dashboard.recentActivity: "/api/dashboard/activity"`

当前后端路由已补齐这两个接口（见 `app/routers/dashboard.py`），前端可直接联调。  

---

## 7. Python SDK（爬虫端接入方式）

位置：`sdk/crawler_client.py`  
提供：
- `CrawlerClient`：同步 requests 客户端
- `AsyncCrawlerClient`：异步 httpx 客户端
- base_url 归一化：支持传站点根、`/api` 前缀、`/pa` 前缀等（最终归到 `/pa/api`）
- 关键方法：
  - `register_crawler(name)`
  - `heartbeat(crawler_id, status, payload, device_name)`
  - `start_run` / `finish_run`
  - `log(crawler_id, level/message/run_id/device_name)`
  - `fetch_commands` / `ack_command`
  - 自动心跳线程/协程（`start_auto_heartbeat` / `stop_auto_heartbeat`）

这使得“爬虫端接入”不需要手写 HTTP 调用，减少对接成本与错误率。

---

## 8. 数据模型（按业务域总结）

> 这里不逐字段列完（会非常长），而是按“每张表解决什么问题”总结，同时给出关键关联，便于你后续做报表/扩展。

### 8.1 账号与权限域
- `users`：用户主体（含角色、主题、头像、日志配额）
- `user_groups`：用户组（功能开关：爬虫/文件）
- `user_sessions`：会话表（多设备/记住我/撤销）
- `invite_codes` / `invite_usages`：邀请码与使用记录
- `system_settings`：系统设置（如注册模式）

### 8.2 爬虫域
- `api_keys`：API Key（可公开、可分组、可禁用、记录最近使用信息）
- `crawler_groups`：分组（归属用户，可绑定多个 key 与 crawler）
- `crawlers`：工程（按用户内 local_id 编号，绑定 api_key，支持隐藏/置顶/公开 slug）
- `crawler_runs`：运行记录（running/success/failed）
- `crawler_heartbeats`：心跳事件（状态、payload、来源 IP、device_name）
- `log_entries`：日志（level、message、ts、ip、device、关联 run/crawler/api_key）
- `crawler_commands`：指令（pending/done 等状态、payload、result、过期时间）
- `crawler_access_links`：公开链接（slug → crawler/api_key/group）
- `crawler_config_templates` / `crawler_config_assignments`：配置模板与配置下发
- `crawler_alert_rules` / `crawler_alert_states` / `crawler_alert_events`：告警体系

### 8.3 文件域
- `file_api_tokens`：文件令牌（up- 前缀，支持 IP/CIDR 白名单）
- `file_entries`：文件元数据（对象路径、hash、可见性、归属）
- `file_access_logs`：访问审计

### 8.4 配置域
- `app_configs`：app 配置（JSON 字符串、版本、enabled、置顶）
- `app_config_read_logs`：公开读取访问日志

### 8.5 审计域
- `operation_audit_logs`：关键变更审计（API Key/分组等）

---

## 9. 迁移与启动行为（数据库如何“自动就绪”）

### 9.1 Alembic 迁移

迁移目录：`migrations/`  
迁移特点：
- `migrations/env.py` 目标元数据：`app.models.Base.metadata`
- SQLite 自动启用 batch 模式（兼容 ALTER TABLE 能力不足的问题）

关键迁移（按文件名可读性）：
- `364081709abf_init_schema.py`：初始化 schema（唯一一次允许 `create_all`）
- `f7d2a1c3d4e5_remove_unique_on_crawlers_api_key_id.py`：解除 `crawlers.api_key_id` 唯一约束（允许一 Key 多工程）
- `b1a2c3d4e5f6_add_user_sessions_and_avatar.py`：新增头像字段 + 会话表
- `c9a1b6d7e8f0_add_app_config_tables.py`：新增配置中心表
- `a2b3c4d5e6f7_add_enabled_pinned_to_app_configs.py`：配置中心增加 enabled/pinned_at

### 9.2 启动时自动迁移与兜底

存在两处“自动迁移/校准”：
- `scripts/prestart.py`：容器启动前执行（等待 DB → alembic upgrade head）
- `app/main.py` startup：应用启动时执行 `_run_alembic_upgrade_head()`
  - 策略：优先 `upgrade head`；必要时对历史库执行 `stamp head` 做版本对齐

此外还有兼容性兜底：
- `app/database.py` `_ensure_extra_columns()`：在“不使用迁移/旧库”的情况下补齐新增列，并做“移除旧唯一约束”的尽力清理（尤其照顾 SQLite autoindex 的情况）

结论：
- 该项目倾向于“部署时自动把库迁移到可运行状态”，降低手工操作门槛；
- 但生产环境仍建议：迁移可观测、可回滚、可审计（CI/CD 中显式执行迁移往往更稳）。

---

## 10. 部署与运维（怎么跑起来、怎么稳定跑）

### 10.1 Docker Compose 一键部署（推荐）

入口：`docker-compose.yaml`  
组成：
- `backend`：FastAPI（默认暴露 9093 给内部网络，卷挂载 `./data`、`./logs`）
- `frontend`：Next.js（内部 3000）
- `reverse-proxy`：Nginx（对外 `DOCKER_PROXY_PORT`，默认 8080）

数据持久化：
- `./data`：SQLite 数据库 + `data/files` 上传对象（重要）
- `./logs`：应用日志（重要）

### 10.2 本地开发（后端）

后端依赖管理使用 `uv`（见 `pyproject.toml` 与 `uv.lock`）：
- 启动：`uvicorn app.main:get_app --reload --host 0.0.0.0 --port 9093`

注意：
- 仓库内存在 `test/` pytest 用例，已在 `pyproject.toml` 的
  `project.optional-dependencies.test` 中补齐 pytest 依赖（仍建议后续补充 CI）。

### 10.3 本地开发（前端）

进入 `frontend/`：
- `pnpm install`
- `pnpm dev`（默认 3000）

关键环境变量：
- `NEXT_PUBLIC_API_BASE_URL`：推荐生产 `/api`；开发可用 `http://localhost:9093`
- `BACKEND_ORIGIN`：Next rewrites 的目标后端（默认 `http://localhost:9093`）

### 10.4 反向代理与真实 IP

`deploy/nginx/default.conf` 做了：
- `set_real_ip_from` + `real_ip_recursive on`：从 `X-Forwarded-For` 恢复真实 IP
- 对后端透传 `X-Real-IP`、`X-Forwarded-*`（不同 location 略有差异）

后端侧：
- `ProxyHeadersMiddleware` + uvicorn `--proxy-headers`（需配置可信上游 IP）

建议：
- 生产环境务必收敛 `FORWARDED_TRUSTED_IPS` / `FORWARDED_ALLOW_IPS`，避免被伪造头欺骗来源 IP。

### 10.5 安全与合规建议（运维侧）

必须做：
- 修改 `SECRET_KEY` 与 `ROOT_ADMIN_PASSWORD`
- 上 HTTPS（跨域 Cookie 场景需要 `Secure=true` 且 `SameSite=None`）
- 限制公开链接（`allow_logs` 默认建议 false）
- 定期备份 `data/`（SQLite + 文件对象），并监控体积增长

---

## 11. 风险评估与改进建议（按优先级）

> 这里是“看完后立刻能提升稳定性/安全性/可维护性”的建议，供你决定是否进入下一轮迭代。

### P0（强烈建议尽快处理）
1) **API Key 明文存储**：`api_keys.key` 注释明确提示“生产建议哈希”。  
   - 风险：数据库泄露会直接暴露所有爬虫接入钥匙。  
   - 方向：只在创建/轮换时返回明文，库内存 hash + 前缀；校验时 hash 对比。

2) **日志存储增长风险**：日志入库 + 查询是核心，但会成为最大数据量来源。  
   - 现有已有配额与滚动删除，是正确方向；仍建议：
   - 方向：为 `log_entries` 做更明确索引策略（crawler_id、ts、level_code），并考虑冷热分离（如按月分表/外部日志系统）。

3) **单实例内存频控/缓存**：`_LOG_RATE_BUCKETS`、`_PUBLIC_STATS_CACHE` 等对多实例部署不一致。  
   - 方向：Redis/集中式限流与缓存。

### P1（体验与一致性）
1) **路由归属冲突（/files 等）**：生产反代默认 `/files` 由后端接管，但前端也存在 `/files` 页面。  
   - 方向：明确“哪一侧提供 UI”，并调整 Nginx 或 Next rewrites。

2) **注册后会话不入表（已优化）**：注册成功会创建 `user_sessions`，token 携带 `sid`，
   会话治理与登录行为一致。

3) **enable_files 未强制生效（已优化）**：文件路由已增加 gating，
   未启用文件功能的用户组会被拦截。

### P2（工程化与长期维护）
1) **后端测试依赖未声明（已优化）**：已在 `pyproject.toml` 增加
   `project.optional-dependencies.test`（含 pytest）。
   - 方向：补充 CI（例如在流水线中执行 `pytest`）。

2) **重复迁移触发点**：容器 prestart 与 app startup 都会尝试迁移。  
   - 方向：保留一个即可（通常推荐 prestart/entrypoint 统一迁移）。

---

## 12. 独立组件说明：decoy-admin-honeypot（安全研究/教学用）

该组件用于“/admin 诱捕假后台”，与 AllYend 主站无强耦合，主要用途：
- 让未授权访问者进入“假后台”，并把其操作记录到 SQLite（`data/honeypot.db`）
- 管理员登录后可访问“真后台”查看/导出诱捕日志（CSV），用于分析攻击行为

关键点：
- 代码入口：`src/server.js`
- 模板：`views/fake/*`、`views/real/*`
- 静态：`public/css/style.css`
- 默认策略强调“安全伪下载”，避免实际危害（仍需你自行评估合规与风险）

建议：如果用于生产互联网环境，请务必明确合规边界、日志脱敏、访问控制、以及告警策略。

---

## 13. 快速索引（我想改/查某类问题，去哪）

- 登录/会话/Cookie：`app/routers/auth.py`、`app/dependencies.py`
- API Key：`app/routers/auth.py`、`app/models.py#APIKey`
- 爬虫接入：`app/routers/crawlers.py`（`/pa/api/**`）
- 日志查询/统计/配额：`app/routers/crawlers.py`（log_* 函数族）
- 文件上传下载/令牌：`app/routers/files.py`
- 管理后台 API：`app/routers/admin.py`（`/hjxgl/api/**`）
- 配置中心：`app/routers/configs.py`（`/api/configs/**`、`/pz`）
- Alembic：`migrations/env.py`、`migrations/versions/*`
- Docker/Nginx：`docker-compose.yaml`、`deploy/nginx/default.conf`
- 前端 API 封装：`frontend/src/lib/api/*`
---

## 14. 本轮全库优化落地记录（2026-01-12）

> 目标：在不改变业务语义的前提下，把前后端的质量门禁跑通，并把“明显不应入库的产物”清理出仓库，让项目可持续迭代（尤其是 CI/CD 与多人协作时）。

### 14.1 前端（`frontend/`）“全量优化到同一标准”

已达成的统一标准（可作为后续 CI 门禁）：
- `pnpm -C frontend lint`：ESLint + Stylelint **0 warning / 0 error**
- `pnpm -C frontend typecheck`：TypeScript `strict` 模式 **通过**
- `pnpm -C frontend test`：Vitest **通过**

关键修复点（按影响面归类）：
- **ESLint 质量门禁清零**：修复冗余布尔转换、空 catch 块、未使用变量/导入、错误的 hooks 依赖数组等，确保 `--max-warnings=0` 也能通过。
- **类型导入一致性**：将 `import()` type annotation 改为 `import type { ... }`（符合 `@typescript-eslint/consistent-type-imports`），减少类型系统噪声与构建差异。
- **退出登录体验优化**：`frontend/src/store/auth-store.ts` 的 `logout()` 先清空本地状态，再尝试调用后端登出接口；网络失败不影响 UI 立即退出（更贴近真实产品体验）。
- **样式规范对齐**：修复 `globals.css` 的 `comment-empty-line-before`，避免 stylelint 在 CI 中阻塞。
- **格式统一**：对本轮修改过的 TS/TSX/CSS 进行了 Prettier 格式化，尽量保证同一代码风格与可读性。

### 14.2 后端（`app/`）本轮已落地修复回顾

本轮后端侧主要是“可靠性与一致性”优化，避免前端联调与生产运行出现边界行为不一致：
- **真实 IP/白名单判定统一**：抽象并统一请求来源 IP 解析与 IP/CIDR 白名单判断（新增 `app/utils/request_utils.py`），避免各路由自行判断导致的差异与安全风险。
- **文件域启用开关一致性**：补齐 `enable_files` gating，使文件域与爬虫域的“用户组能力开关”一致生效。
- **注册后会话一致化**：注册成功后同样创建 `user_sessions` 并在 JWT 中携带 `sid`，会话治理与登录行为一致。
- **启动迁移策略更稳健**：`app/main.py` 改为 lifespan 管理，优先 upgrade，stamp 只在可判断的兜底场景执行，降低误 stamp 风险。
- **仪表盘占位 API 补齐**：增加 `/api/dashboard/overview`、`/api/dashboard/activity`，避免前端页面缺接口导致空白或报错。

### 14.3 仓库清洁度（统一“可提交内容”的边界）

为避免“运行产物/临时脚本”污染主仓库，本轮已清理并加规则防回归：
- 删除 Playwright/Vitest 运行产物：`frontend/test-results/.last-run.json`，并在 `frontend/.gitignore` 忽略 `test-results/`。
- 删除误提交的临时输出与一次性脚本：`next-start.err`、`next-start.log`、`tmp_auth_lines.txt`、`tmp_slice.txt`、`inspect_command_form.py`、`update_mutations_refactor.py`，并在根 `.gitignore` 增加对应忽略规则。

### 14.4 本机验证结果（可复现命令）

后端：
- `uv run python -m compileall app -q`
- `uv run pytest -q`（9 passed；存在 SQLAlchemy drop_all 的循环外键排序警告，不影响测试结果）

前端：
- `pnpm -C frontend lint`
- `pnpm -C frontend typecheck`
- `pnpm -C frontend test`

### 14.5 已知警告与后续建议（不阻塞，但建议纳入迭代计划）

- `pytest` 的 SQLAlchemy 警告（drop_all 外键环）：测试 teardown 时存在表间循环依赖，建议后续用 `use_alter=True` 标记环或调整外键设计/拆分 teardown 顺序，降低测试噪声。
- Vitest 输出依赖提示（`baseline-browser-mapping` 过旧、Vite CJS Node API deprecation）：不影响功能，但建议在依赖升级窗口统一处理，避免未来升级时一次性踩坑。

