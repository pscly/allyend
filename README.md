# AllYend

AllYend 是一个面向团队的爬虫监控与文件中转平台，集成以下能力：

- **爬虫接入中心**：统一以 `/pa/api` 为入口，提供注册 / 心跳 / 运行 / 日志上报，并支持基于 IP 的溯源。
- **快捷匿名链接**：可以为爬虫或 API Key 生成自定义的访问 slug，例如 `https://host/pa/mybot01` 供外部伙伴查看日志。
- **文件中转站**：支持匿名上传、登录用户网盘、API 令牌上传，且可按 IP / 网段限制访问。
- **权限体系**：管理员可创建分组、邀请码、设置注册策略，并审计文件访问日志。
- **个性化主题**：登录用户可在仪表盘自定义主题色彩与暗色模式。

> 默认站点名称为 **AllYend**，可在 `.env` 中调整并同步到前端品牌。

## 快速开始

1. 初始化配置：
   ```bash
   copy .env.example .env  # Linux/Mac 使用 cp
   ```
   - 设置 `SECRET_KEY`、`ROOT_ADMIN_PASSWORD` 等关键字段。
   - `ROOT_ADMIN_INVITE_CODE` 将在首次运行时生成超级管理员；其默认用户名来自 `ROOT_ADMIN_USERNAME`。

2. 安装依赖与运行开发服务：
   ```bash
   python -m pip install -U uv
   uv venv
   uv sync
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 9093
   ```

3. 浏览器访问 `http://localhost:9093`：
   - 使用 root 管理员（`.env` 中配置）登录。
   - 在管理控制台生成邀请码或调整注册策略。

## 平台流程

```mermaid
flowchart LR
    subgraph Client
        A[SDK / Cron Job] -->|上报| B[/pa/api]
        C[浏览器] -->|仪表盘| D[/dashboard]
        C -->|文件中心| E[/files]
    end

    subgraph Backend[AllYend]
        B --> F[FastAPI Router]
        E --> G[Files Router]
        D --> H[Dashboard Router]
        F --> I[(Database)]
        G --> I
        H --> I
    end

    subgraph Storage
        J[SQLite/PostgreSQL]
        K[文件存储目录]
    end

    I --> J
    G --> K
```

## 模块概览

### 1. 爬虫接入（/pa/api）

| 功能 | 方法 | 路径 |
| ---- | ---- | ---- |
| 注册 / 获取爬虫 ID | POST | `/pa/api/register` |
| 上报心跳 | POST | `/pa/api/{crawler_id}/heartbeat` |
| 运行开始 / 结束 | POST | `/pa/api/{crawler_id}/runs/start`<br>`/pa/api/{crawler_id}/runs/{run_id}/finish` |
| 日志上报 | POST | `/pa/api/{crawler_id}/logs` |
| 我的爬虫 / 日志 | GET | `/pa/api/me`<br>`/pa/api/me/logs` |
| 快捷链接管理 | GET/POST/DELETE | `/pa/api/links` |

- 所有上报接口会记录来源 IP，并回填到运行与日志中。
- 快捷链接 slug 最少 6 位，可指向单个爬虫或某个 API Key：
  ```bash
  curl -X POST /pa/api/links \
    -H "Content-Type: application/json" \
    -d '{"target_type":"crawler","target_id":1,"slug":"allyend-demo"}'
  ```
  访问 `https://host/pa/allyend-demo/logs` 即可匿名查看。

### 2. 文件中转服务（/files）

- **用户网盘**：登录后访问 `/files`，可选择可见性（私有 / 分组 / 公开）。
- **API 令牌**：
  - 创建：`POST /files/api/tokens`
  - 上传：`POST /files/api/tokens/{token}/up`
  - 列表：`GET /files/api/tokens/{token}`
- **访问限制**：令牌支持 `allowed_ips` 与 `allowed_cidrs`，且所有操作会写入访问日志。
- **公开下载**：`GET /files/<文件名>`（最新上传优先，首页直接展示列表）。

示例：
```bash
# 使用令牌上传（限制外网访问）
curl -F "file=@data.csv" -F "visibility=group" https://host/files/<token>/up
```

### 3. 管理控制台（/admin）

- 切换注册模式：开放 / 邀请 / 关闭。
- 创建/撤销邀请码（可绑定分组、设置过期与次数）。
- 为用户分配分组、调整角色、禁用账户。
- 查看文件访问日志（全部或限定用户范围）。

## 数据模型

核心表（摘要）：

- `users`：包含角色（user/admin/superadmin）、分组、邀请来源等字段。
- `user_groups`：控制功能开关（爬虫、文件）。默认提供普通组与管理员组。
- `invite_codes` / `invite_usages`：记录邀请码及使用审计。
- `crawler_access_links`：匿名快捷访问映射。
- `file_entries` / `file_api_tokens` / `file_access_logs`：文件元数据与访问流水。
- `system_settings`：保存注册模式等动态配置。

## SDK 示例

```python
from sdk.crawler_client import CrawlerClient

client = CrawlerClient(base_url="http://localhost:9093/pa", api_key="<你的APIKey>")
crawler = client.register_crawler("news_spider")
run = client.start_run(crawler_id=crawler["id"])
client.log(crawler_id=crawler["id"], level="INFO", message="启动成功", run_id=run["id"])
client.finish_run(crawler_id=crawler["id"], run_id=run["id"], status="success")
```

> 注意：`base_url` 需指向 `/pa` 前缀。

## 配置清单

`.env` 关键项：

- `SITE_NAME`：品牌名称。
- `ROOT_ADMIN_USERNAME` / `ROOT_ADMIN_PASSWORD`：超级管理员。
- `ROOT_ADMIN_INVITE_CODE`：超级管理员专用邀请码。
- `DEFAULT_ADMIN_INVITE_CODE`、`DEFAULT_USER_INVITE_CODE`：预置邀请码（可选）。
- `ALLOW_DIRECT_SIGNUP`：是否允许无邀请码注册。
- `FILE_STORAGE_DIR`：文件存储目录。
- `LOG_DIR`：本地日志目录（默认 logs/allyend.log，支持滚动保存）。

## 后续路线

- 指标看板与定制化告警。
- Webhook / 回调机制，联动外部系统。
- 更细粒度的文件标签与过期策略。

欢迎贡献 Issue 或 Pull Request，共同完善 AllYend。
