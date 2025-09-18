# Crawler Hub（爬虫信息汇总与监控平台）

一个用于汇总爬虫信息、监控运行状态、收集日志的全栈示例项目，涵盖：
- 后端：FastAPI + SQLAlchemy（SQLite 默认）
- 前端：Jinja2 模板与自定义主题系统
- 身份认证：JWT（Cookie / Authorization Bearer）
- SDK：Python 客户端，支持可选的 print 替换
- 仪表盘能力：API Key 管理、日志筛选、多应用联查、公开展示页
- 依赖管理：uv（Astral）

## 快速开始

1. 复制环境变量模板并填写密钥
   ```bash
   copy .env.example .env  # PowerShell 可用：Copy-Item .env.example .env
   ```
   - `SITE_ICP` 可配置备案号，留空则不展示

2. 安装 uv（如本机未安装）
   ```bash
   python -m pip install -U uv
   ```

3. 创建虚拟环境并安装依赖
   ```bash
   uv venv
   uv sync
   ```

4. 运行开发服务器（默认端口 9093）
   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 9093 --reload
   ```

访问：http://localhost:9093

## 功能亮点
- **主题个性化**：用户可以在仪表盘中选择预设主题、微调主色/背景并切换暗色模式，配置持久化存储
- **日志筛选中心**：支持多爬虫同时筛选，按日期与等级（0/10/20/30/40/50）组合查询，并限制返回条数
- **公开展示页**：可将指定 API Key 或爬虫设置为公开，未登录用户访问 `/public` 即可查看概要与公开日志
- **SDK print 捕获**：通过 `client.printer` 或 `client.capture_print`，将爬虫侧的 `print` 输出同步上报日志

## SDK 使用示例
```python
from sdk.crawler_client import CrawlerClient

client = CrawlerClient(base_url="http://localhost:9093", api_key="<你的APIKey>")

# 注册爬虫（按名称去重）
crawler = client.register_crawler(name="news_spider")

# 开始一次运行
run = client.start_run(crawler_id=crawler["id"])
client.log(crawler_id=crawler["id"], level="INFO", message="启动成功", run_id=run["id"])

# 心跳（建议定时调用）
client.heartbeat(crawler_id=crawler["id"])

# 可选：把 print 输出同步到平台
printer = client.printer(crawler_id=crawler["id"], run_id=run["id"], default_level="INFO")
printer("爬虫启动完成")

# 或使用上下文管理器
with client.capture_print(crawler_id=crawler["id"], run_id=run["id"], default_level="INFO"):
    print("这条消息会进入平台", level="WARNING")

# 结束运行
client.finish_run(crawler_id=crawler["id"], run_id=run["id"], status="success")
```

## 公开访问（可选）
- 在仪表盘中将 API Key 或爬虫切换为公开，系统会生成分享链接（形如 `/public?slug=xxxx`）
- 未登录用户可访问 `/public` 查看公开的 Key 列表与日志概览

## 目录结构
```
app/
  auth.py            # 认证与安全工具
  config.py          # 配置加载（.env）
  constants.py       # 常量（日志等级、主题预设）
  database.py        # SQLAlchemy 初始化与简易迁移
  main.py            # FastAPI 入口、路由注册
  models.py          # ORM 模型
  schemas.py         # Pydantic 模型
  dependencies.py    # 依赖项（DB 会话等）
  routers/
    auth.py          # 登录/注册、API Key 管理
    crawlers.py      # 爬虫注册、心跳、运行、日志 API
    dashboard.py     # 仪表盘与页面路由（含公开页）
  templates/         # Jinja2 模板
  static/            # 静态资源（主题化样式）
sdk/
  crawler_client.py  # Python SDK
```

## 生产注意事项
- API Key 建议仅展示一次并使用哈希存储（示例为简化未哈希）
- JWT 私钥务必改为强随机值，并设置安全 Cookie 属性
- SQLite 仅适合开发与单机小规模部署，生产建议切换到 MySQL/PostgreSQL
- 建议增加限流、审计日志、权限模型、Webhook 通知等

## 许可证
本示例仅供学习参考。
