"""
应用入口：
- FastAPI 初始化、模板/静态资源、路由挂载
- 启动时执行 Alembic 迁移与数据自检
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .config import settings
from .database import ensure_database_schema, bootstrap_defaults
from .routers import auth as auth_router
from .routers import crawlers as crawlers_router
from .routers import dashboard as dashboard_router
from .routers import files as files_router
from .routers import md as md_router
from .routers import admin as admin_router




def _configure_logging() -> None:
    log_dir = Path(settings.LOG_DIR or "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "allyend.log"
    root = logging.getLogger()

    # 统一格式
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # 确保文件日志处理器存在（幂等）
    file_handler = None
    for h in root.handlers:
        if isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == str(log_file):
            file_handler = h
            break
    if file_handler is None:
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # 将相同的文件处理器挂到 uvicorn.access（避免重复挂载）
    ua_logger = logging.getLogger("uvicorn.access")
    has_ua_file = any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == str(log_file) for h in ua_logger.handlers)
    if not has_ua_file:
        ua_logger.addHandler(file_handler)

    # 确保控制台处理器存在（幂等）
    has_console = any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    if not has_console:
        console = logging.StreamHandler(stream=sys.stdout)
        console.setFormatter(formatter)
        root.addHandler(console)

    # 设定日志级别
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)

_configure_logging()
app = FastAPI(title=settings.SITE_NAME, version="0.2.0")

# CORS（按需开放）
cors_origins = settings.FRONTEND_ORIGINS or ["http://localhost:3000"]
if "*" in cors_origins:
    configured_origins = ["*"]
else:
    configured_origins = cors_origins

# 代理头中间件（从 X-Forwarded-* / Forwarded 恢复真实 client/scheme/host）
# 注意：默认仅信任 127.0.0.1/::1；若 .env 配置包含 "*"，则信任所有上游（适合仅内网可达的后端）。
_trusted = settings.FORWARDED_TRUSTED_IPS
_trusted_value = "*" if (isinstance(_trusted, (list, tuple, set)) and "*" in _trusted) else _trusted
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=_trusted_value)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态资源（使用绝对路径，避免工作目录差异导致 404）
_BASE_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def _run_alembic_upgrade_head() -> None:
    """在本地/开发模式下自动执行 Alembic 升级。

    - 优先使用应用配置中的 DATABASE_URL；
    - 通过代码调用 Alembic，避免必须手动执行命令；
    - 幂等：若已在 head，不会做任何变更。
    """
    try:
        from alembic.config import Config  # type: ignore
        from alembic import command  # type: ignore

        root = Path(__file__).resolve().parent.parent
        cfg = Config(str(root / "alembic.ini"))
        # 使用 app 配置覆盖 alembic.ini，保证本地与容器一致
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.upgrade(cfg, "head")
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("alembic upgrade 失败：%s", exc)


@app.on_event("startup")
def on_startup():
    # 1) 先确保基础结构（新装场景）
    ensure_database_schema()
    # 2) 再执行 Alembic 迁移（已有库与结构差异统一在这里处理）
    _run_alembic_upgrade_head()
    # 3) 引导默认数据
    bootstrap_defaults()
    # 4) 迁移执行可能修改了 logging（alembic.ini），此处重新校准日志到控制台+文件
    _configure_logging()


# 健康检查与就绪探针（便于排查“卡住”）
@app.get("/health")
def healthcheck():
    """返回应用健康状态，用于本地/容器探活"""
    return {"status": "ok"}


# 路由注册
app.include_router(auth_router.router)
app.include_router(crawlers_router.router)
app.include_router(crawlers_router.public_router)
app.include_router(files_router.router)
app.include_router(admin_router.router)
app.include_router(dashboard_router.router)
app.include_router(md_router.router)


# 便于 uv run 直接引用
def get_app():
    return app


