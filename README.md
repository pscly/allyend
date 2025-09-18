# Crawler Hub（爬虫信息汇总与监控平台）

一个用于汇总爬虫信息、监控运行状态、收集日志的全栈示例项目：
- 后端：FastAPI + SQLAlchemy（SQLite）
- 前端：Jinja2 模板（简易仪表盘、登录/注册）
- 身份认证：JWT（Cookie / Authorization Bearer）
- SDK：Python 客户端，便于爬虫工具上报状态/日志
- 依赖管理：uv（Astral）

## 快速开始

1. 复制环境变量并填写密钥
```bash
copy .env.example .env  # Windows PowerShell 可改用：Copy-Item .env.example .env
```

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

## 认证与 API Key
- 访问首页先登录/注册
- 进入仪表盘后可管理 API Key（用于爬虫上报）
- 爬虫通过 `X-API-Key: <key>` 调用 API

## SDK 使用（示例）
```python
from sdk.crawler_client import CrawlerClient

client = CrawlerClient(base_url="http://localhost:9093", api_key="<你的APIKey>")

# 注册爬虫（可按名称去重复用）
crawler = client.register_crawler(name="news_spider")

# 开始一次运行
run = client.start_run(crawler_id=crawler["id"])  # 返回 run_id
client.log(crawler_id=crawler["id"], level="INFO", message="启动成功", run_id=run["id"]) 

# 心跳（建议定时调用）
client.heartbeat(crawler_id=crawler["id"]) 

# 结束运行
client.finish_run(crawler_id=crawler["id"], run_id=run["id"], status="success")
```

## 目录结构
```
app/
  auth.py           # 认证与安全工具
  config.py         # 配置加载（.env）
  database.py       # SQLAlchemy 初始化
  main.py           # FastAPI 入口、路由注册
  models.py         # ORM 模型
  schemas.py        # Pydantic 模型
  dependencies.py   # 依赖项（DB会话等）
  routers/
    auth.py         # 登录/注册、API Key 管理
    crawlers.py     # 爬虫注册/心跳/运行/日志 API
    dashboard.py    # 仪表盘与页面路由
  templates/        # Jinja2 模板
  static/           # 静态资源
sdk/
  crawler_client.py # Python SDK
```

## 生产注意事项
- API Key 建议仅展示一次并使用哈希存储（示例为简化未哈希）
- JWT 私钥务必改为强随机值，并设置安全 Cookie 属性
- SQLite 仅适合开发与单机小规模部署，生产建议切换到 MySQL/PostgreSQL
- 增加限流、审计日志、权限模型等

## 许可证
本示例仅供学习参考。
