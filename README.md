# AllYend

爬虫监控 + 日志聚合 + 远程指令 + 文件中转 的一体化平台

---

## 功能特性

- 账户与分组
  - 注册/登录（可配置：开放/邀请码/关闭），Cookie 会话安全
  - 用户组（开启/关闭“爬虫功能”“文件服务”），主题配色与深浅色
- API Key 管理
  - 多个 Key，分组归类，支持公开/私有、IP/CIDR 白名单、轮换、审计
- 爬虫接入与监控（路径前缀 `/pa`）
  - 注册/心跳、运行开始/结束、日志上报（等级/编码）、来源 IP 与设备名
  - 远程指令下发与回执（fetch + ack），工程置顶/隐藏
  - 配额与清理：单工程上限（行/字节）与用户总配额（字节），超限滚动裁剪
  - 统计接口与公开页（按 slug 暴露只读数据）
- 文件中转与网盘
  - 令牌上传（`up-` 前缀）、可见性（private/group/public/disabled）
  - 别名下载去重：`report.pdf`、`report-1.pdf`、`report-2.pdf` …
  - Web 页面：文件列表、管理页；完整访问审计
- 管理后台（路径前缀 `/hjxgl`）
  - 用户/分组/邀请码/注册策略管理，日志用量统计
- 通用回显接口 `/md`
  - GET/POST 统一回显 query/form/json，附时间戳、IP、URL
- SDK 与前端集成
  - Python SDK（同步/异步）位于 `sdk/crawler_client.py`
  - 前端 API 客户端与类型定义见 `docs/frontend-sdk.md`

---

## 技术栈与架构

- 后端：FastAPI + SQLAlchemy 2.x + Pydantic Settings，Jinja2 模板
- 数据库：默认 SQLite（`data/app.db`），可切换 MySQL/PostgreSQL（配置 `DATABASE_URL`）
- 网关：Nginx 统一反代（`deploy/nginx/default.conf`）
- 前端：Next.js 14（`frontend/`）
- 日志：滚动文件 `logs/allyend.log` + 审计表 `operation_audit_logs`/`file_access_logs`
- 容器：`Dockerfile.backend` + `docker-compose.yaml`

## 系统架构图

```mermaid
graph LR
  subgraph Client
    BROWSER[Web 浏览器<br/>Next.js 前端] -->|Cookie 会话| NGINX[Nginx 反向代理]
    CRAWLER[爬虫/Agent<br/>Python SDK] -->|X-API-Key| NGINX
  end

  NGINX -->|/api, /pa, /files, /static| API[FastAPI 后端]
  NGINX -->|/| FE[Next.js 前端(SSR/静态)]

  API -->|SQLAlchemy ORM| DB[(数据库<br/>SQLite/MySQL/PostgreSQL)]
  API -->|对象写入/读取| FS[(文件存储<br/>data/files)]
  API -->|访问/操作审计| AUDIT[(审计与日志)]
  API -->|SMTP/Webhook| ALERTS[告警渠道]

  classDef comp fill:#E6F7FF,stroke:#409EFF,stroke-width:1px;
  class BROWSER,CRAWLER,NGINX,API,FE,DB,FS,AUDIT,ALERTS comp;
```

## 典型流程图（爬虫与文件）

```mermaid
flowchart TD
  A[SDK: 注册工程] --> B[POST /pa/api/register<br/>Header: X-API-Key]
  B --> C{返回 Crawler ID?}
  C -- 是 --> D[POST /pa/api/{id}/runs/start]
  D --> E[周期日志上报<br/>POST /pa/api/{id}/logs]
  E --> F[周期心跳<br/>POST /pa/api/{id}/heartbeat]
  F --> G[拉取指令<br/>POST /pa/api/{id}/commands/next]
  G --> H{有指令?}
  H -- 有 --> I[执行并回执<br/>POST /pa/api/{id}/commands/{cmd}/ack]
  H -- 无 --> F
  I --> F
  C -- 否 --> A

  subgraph 文件中转（可选）
    U[客户端/服务: 拿到 up-令牌] --> V[POST /files/{token}/up<br/>Form: file + meta]
    V --> W[保存对象 & 记录 FileEntry/审计]
    W --> X[GET /files/{别名或 up-令牌}?download=1]
  end
```

---

## 目录结构（节选）

```
app/                    # FastAPI 应用
  ├─ main.py            # 应用入口，路由挂载，迁移/初始化
  ├─ config.py          # 配置加载（.env, UTF-8）
  ├─ database.py        # 数据库引擎/Session/初始化与轻量列升级
  ├─ models.py          # ORM 模型
  ├─ routers/           # 路由模块（auth/crawlers/files/dashboard/admin/md）
  └─ templates/         # Jinja2 模板（页面）
frontend/               # Next.js 前端工程
sdk/                    # Python SDK（同步/异步客户端）
deploy/nginx/           # Nginx 反向代理配置
migrations/             # 迁移文件（当前运行时走 create_all + 轻量升级）
README.md               # 本说明
.env.example            # 环境变量模板
```

---

## 快速开始

### 方案 A：Docker 一键启动（推荐）

1) 准备配置

```bash
cp .env.example .env
# 按需修改：SECRET_KEY、ROOT_ADMIN_*、FRONTEND_ORIGINS、DATABASE_URL 等
```

2) 启动

```bash
docker compose up -d --build
# 访问：前端 http://localhost:8080    后端健康检查 http://localhost:8080/api/health
```

- 数据目录与日志目录默认挂载到宿主机：`./data`、`./logs`
- 生产环境请将反代与 `FORWARDED_*`、Cookie、CORS 相关配置收敛到你的域名与网段

### 方案 B：本地开发（后端）

- 前置：Python 3.10+（建议 3.12）、`uv` 包管理器

```bash
# 安装依赖（使用 uv，尊重仓库锁文件）
pip install -U uv
uv sync

# 启动开发服务（默认 9093）
uvicorn app.main:get_app --reload --host 0.0.0.0 --port 9093
# 健康检查：http://localhost:9093/health
# 访问日志（可选，建议在 Uvicorn 0.30+ 显式开启）：
# uvicorn app.main:get_app --reload --host 0.0.0.0 --port 9093 --access-log
```

- 首次启动会自动：创建 `data/app.db`、建表、写入默认用户组与邀请码、创建超级管理员
- 默认管理员用户名：`.env` 中的 `ROOT_ADMIN_USERNAME`；密码取 `ROOT_ADMIN_PASSWORD`（未设置时退回 `SECRET_KEY`）

### 方案 C：本地开发（前端）

- 前置：Node.js ≥ 22，pnpm ≥ 9

```bash
cd frontend
pnpm install
# 连接后端直连开发：
#   将 .env 中 NEXT_PUBLIC_API_BASE_URL 改为 http://localhost:9093
#   或通过 Nginx 反代保持为 /api
pnpm dev
# 打开 http://localhost:3000
```

---

## 环境变量（常用）

详见 `.env.example`，常见项：

- 站点与安全：`SITE_NAME`、`SECRET_KEY`、`ACCESS_TOKEN_EXPIRE_MINUTES`、`ALGORITHM`
- 数据库：`DATABASE_URL`（默认 `sqlite:///./data/app.db`）
- CORS 与代理：`FRONTEND_ORIGINS`、`FORWARDED_TRUSTED_IPS`（逗号或 JSON 数组）
- 注册与管理员：`ALLOW_DIRECT_SIGNUP`、`ROOT_ADMIN_USERNAME`、`ROOT_ADMIN_PASSWORD`、`ROOT_ADMIN_INVITE_CODE`、`DEFAULT_ADMIN_INVITE_CODE`、`DEFAULT_USER_INVITE_CODE`
- 文件与日志：`FILE_STORAGE_DIR`、`LOG_DIR`
- 访问日志兜底：`APP_ACCESS_LOG`（默认 true；若已用 `--access-log` 可设为 false 以避免重复）
- 日志限流/配额：`LOG_QUERY_RATE_PER_SECOND`、`DEFAULT_USER_LOG_QUOTA_BYTES`、`DEFAULT_CRAWLER_LOG_MAX_LINES`、`DEFAULT_CRAWLER_LOG_MAX_BYTES`
- Cookie：`COOKIE_SECURE`、`COOKIE_SAMESITE`（lax/strict/none）、`COOKIE_DOMAIN`、`COOKIE_PATH`
- 通知：`SMTP_*`、`ALERT_EMAIL_SENDER`、`ALERT_WEBHOOK_TIMEOUT`
- 前端构建：`NEXT_PUBLIC_API_BASE_URL`、`NEXT_PUBLIC_APP_BASE_URL`

---

## 页面与 API 速览

- 页面
  - `/` 首页、`/dashboard` 仪表盘、`/public` 公共空间
  - `/login`、`/register` 登录与注册（Cookie 会话）
  - `/files` 文件列表、`/files/manage` 管理页
  - 管理后台：`/hjxgl`（页面）
- 认证（JSON API）
  - `POST /api/auth/login`、`POST /api/auth/register`、`GET /api/users/me`、`/logout`
- 文件服务（JSON + 文件流）
  - 令牌管理：`GET/POST/PATCH /files/tokens`、访问审计 `GET /files/api/logs`
  - 上传：`POST /files/{token}/up`（multipart，字段：`file`、可选 `file_name/visibility/description`）
  - 下载/直连：`GET /files/{alias}`（重名自动添加 `-1/-2` 后缀；`?download=1` 强制下载）
- 爬虫接入（前缀 `/pa/api`，请求头 `X-API-Key`）
  - 注册：`POST /pa/api/register`
  - 心跳：`POST /pa/api/{crawler_id}/heartbeat`
  - 运行：`POST /pa/api/{crawler_id}/runs/start`、`POST /pa/api/{crawler_id}/runs/{run_id}/finish`
  - 日志：`POST /pa/api/{crawler_id}/logs`
  - 指令：`POST /pa/api/{crawler_id}/commands/next`、`POST /pa/api/{crawler_id}/commands/{command_id}/ack`
  - 我的工程与统计：`GET /pa/api/me` 下的若干 `me/**` 端点（分组、日志、配额、统计等）
- 公开读取（前缀 `/pa`）
  - `GET /pa/{slug}` 页面；`GET /pa/{slug}/api` 及 `logs/usage|stats|logs` 只读数据
- 回显接口
  - `GET/POST /md` 合并回显 query/form/json，附 `time/time2/ip/urls`

> 说明：以上为核心端点摘录，完整定义见 `app/routers/` 目录。

---

## Python SDK（爬虫侧）

文件：`sdk/crawler_client.py`

同步用法：

```python
from sdk.crawler_client import CrawlerClient

with CrawlerClient(base_url="https://example.com/api", api_key="<你的Key>") as cli:
    crawler = cli.register_crawler("news_spider")
    run = cli.start_run(crawler_id=crawler["id"])
    cli.log(crawler_id=crawler["id"], level="INFO", message="启动")
    cli.heartbeat(crawler_id=crawler["id"], payload={"tasks": 1})
```

异步用法：

```python
import asyncio
from sdk.crawler_client import AsyncCrawlerClient

async def main():
    async with AsyncCrawlerClient(base_url="http://localhost:9093", api_key="<Key>") as client:
        crawler = await client.register_crawler("news_spider")
        run = await client.start_run(crawler_id=crawler["id"])
        await client.log(crawler_id=crawler["id"], level="INFO", message="启动")
        await client.heartbeat(crawler_id=crawler["id"], payload={"tasks": 12})
        cmds = await client.fetch_commands(crawler_id=crawler["id"])  # 失败返回 []
        for cmd in cmds:
            await client.ack_command(crawler_id=crawler["id"], command_id=cmd["id"], status="success")

asyncio.run(main())
```

前端使用请参考：`docs/frontend-sdk.md`

---

## 数据库与迁移

- 运行时默认使用 `Base.metadata.create_all` 建表，并在 `app/database.py` 内按需“轻量列升级”（新增列）
- 仓库携带 `migrations/` 目录与 `alembic.ini`，如需规范迁移，请接入 Alembic（生产建议）

---

## 安全与部署建议

- 强制修改 `SECRET_KEY`、`ROOT_ADMIN_PASSWORD`，避免默认值
- 生产环境使用 HTTPS，并将 Cookie 设置为 `SameSite=None` 且 `Secure=true`（跨域前端场景）
- 按实际网络拓扑配置 `FORWARDED_TRUSTED_IPS`，与网关的 `X-Forwarded-*`/`X-Real-IP` 保持一致
- 根据业务调优：日志频控（`LOG_QUERY_RATE_PER_SECOND`）、配额（`DEFAULT_*`）与文件权限

---

## 开发与测试

- 运行测试：

```bash
pytest -q
```

- 代码位置速览：
  - 认证/用户/Key：`app/routers/auth.py`
  - 爬虫/日志/指令：`app/routers/crawlers.py`
  - 文件服务：`app/routers/files.py`
  - 页面与主题：`app/routers/dashboard.py`
  - 管理后台：`app/routers/admin.py`

---

## 附：诱捕式“假后台”演示（可选）

仓库根目录包含一个独立的 Node.js 演示应用（`src/server.js` + `views/`），用于安全研究场景下的 `/admin` 诱捕与日志面板。与 AllYend 主站相互独立，默认不随 Docker 编排启动。

- 启动（可选）：

```bash
pnpm install  # 或 npm install
pnpm start    # 或 npm start
# 访问 http://localhost:3000
```

- 重要提示：该演示仅用于研究与教学，请勿在未授权环境中用于对抗或误导；默认策略为“安全伪下载”。

---

## 许可与版权

本仓库未附带许可证文件。如需开源或商用，请根据实际需求补充合适的 LICENSE 并保留版权标识。
