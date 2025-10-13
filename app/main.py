"""
应用入口：
- FastAPI 初始化、模板/静态资源、路由挂载
- 启动时执行 Alembic 迁移与数据自检
"""
from __future__ import annotations

import logging
import os
import time
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .config import settings
from .database import ensure_database_schema, bootstrap_defaults
from pathlib import Path as _P
from .routers import auth as auth_router
from .routers import crawlers as crawlers_router
from .routers import dashboard as dashboard_router
from .routers import files as files_router
from .routers import md as md_router
from .routers import admin as admin_router
from .routers import configs as configs_router




def _apply_timezone() -> None:
    """根据 .env 中的 TIMEZONE 应用进程时区（影响日志切割的本地午夜）。
    - 优先使用 IANA 时区名（例如：Asia/Shanghai）。
    - 在不支持 tzset 的平台上（如少数环境），静默降级为系统本地时区。
    """
    try:
        if settings.TIMEZONE:
            os.environ["TZ"] = str(settings.TIMEZONE)
            tz_name = getattr(settings, "TIMEZONE", None)

            # 某些平台（Linux/Unix）可即时生效；Windows 可能不支持
            if hasattr(time, "tzset"):
                time.tzset()
    except Exception:
        # 保守处理：不中断应用，仅记录告警
        logging.getLogger(__name__).warning("无法应用时区设置：%s", settings.TIMEZONE)


def _configure_logging() -> None:
    log_dir = Path(settings.LOG_DIR or "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "allyend.log"
    root = logging.getLogger()

    # 统一格式
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # 确保文件日志处理器存在（幂等）
    # 从按大小切割切换为按天切割：本地午夜（受 _apply_timezone 影响）
    file_handler = None
    for h in root.handlers:
        if isinstance(h, (RotatingFileHandler, TimedRotatingFileHandler)) and getattr(h, "baseFilename", None) == str(log_file):
            file_handler = h
            break
    if file_handler is None:
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",
            interval=1,
            backupCount=14,  # 默认保留 14 天，可按需调整
            encoding="utf-8",
            utc=False,  # 使用本地时区（由 _apply_timezone 控制）
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # 统一接管 uvicorn.access：
    # - 开启传播到 root（由 root 的控制台/文件处理器统一输出）
    # - 清空其自带的处理器，避免与 root 重复输出
    ua_logger = logging.getLogger("uvicorn.access")
    ua_logger.setLevel(logging.INFO)
    ua_logger.disabled = False
    ua_logger.propagate = True
    # 清理已有处理器（保守处理：只在存在非文件轮转处理器时清空，避免第三方重复挂载）
    if any(not isinstance(h, (RotatingFileHandler, TimedRotatingFileHandler)) for h in ua_logger.handlers):
        ua_logger.handlers.clear()

    # 确保控制台处理器存在（幂等）
    has_console = any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    if not has_console:
        console = logging.StreamHandler(stream=sys.stdout)
        console.setFormatter(formatter)
        root.addHandler(console)

    # 设定日志级别
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)

_apply_timezone()
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
_AVATAR_DIR = _P(getattr(settings, "FILE_STORAGE_DIR", "data/files")).resolve() / "avatars"
_AVATAR_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/avatars", StaticFiles(directory=str(_AVATAR_DIR)), name="avatars")


class _AccessLogASGI:
    """应用层访问日志兜底（ASGI 包裹器）。

    - 不依赖 Starlette 的 BaseHTTPMiddleware，直接在 ASGI 层拦截 HTTP 请求，
      稳定输出访问日志（即便 Uvicorn 未开启 --access-log）。
    - 日志写入 logger `uvicorn.access`，并通过前面的 _configure_logging 传播到 root，
      从而统一输出到控制台与文件。
    """

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("uvicorn.access")

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        client = scope.get("client")
        addr = f"{client[0]}:{client[1]}" if client else "-"
        # 若有代理头，尽量恢复真实客户端地址（简化版）
        try:
            raw_headers = scope.get("headers") or []
            hdrs = {k.decode("latin1").lower(): v.decode("latin1") for k, v in raw_headers}
            xff = hdrs.get("x-forwarded-for")
            xfp = hdrs.get("x-forwarded-port")
            if xff:
                real_ip = xff.split(",")[0].strip()
                addr = f"{real_ip}:{xfp}" if xfp else real_ip
        except Exception:  # noqa: BLE001
            pass
        method = scope.get("method", "-")
        path = scope.get("path", "/")
        qs = scope.get("query_string", b"")
        if qs:
            try:
                qs_str = qs.decode("utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                qs_str = ""
            if qs_str:
                path = f"{path}?{qs_str}"
        http_version = scope.get("http_version", "1.1")
        status_code = 500

        async def _send(message):
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 200))
            return await send(message)

        try:
            return await self.app(scope, receive, _send)
        finally:
            self.logger.info('%s - "%s %s HTTP/%s" %s', addr, method, path, http_version, status_code)


# 是否启用应用层访问日志兜底（仅记录，不改变 FastAPI 实例供路由/事件注册）
_enable_app_access_log = str(getattr(settings, "APP_ACCESS_LOG", "true")).strip().lower()


def _run_alembic_upgrade_head() -> None:
    """在本地/开发模式下自动执行 Alembic 升级。

    - 优先使用应用配置中的 DATABASE_URL；
    - 通过代码调用 Alembic，避免必须手动执行命令；
    - 幂等：若已在 head，不会做任何变更。
    """
    try:
        from alembic.config import Config  # type: ignore
        from alembic import command  # type: ignore
        from sqlalchemy import create_engine, inspect

        root = Path(__file__).resolve().parent.parent
        cfg = Config(str(root / "alembic.ini"))
        # 使用 app 配置覆盖 alembic.ini，保证本地与容器一致
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

        # 判定：
        # - 如不存在 alembic_version 且库中也不存在核心业务表（如 users），说明是“空库”，执行 upgrade 以按迁移完整建表；
        # - 如不存在 alembic_version 但已存在业务表，视为“历史手动/ORM 建表库”，执行 stamp 以对齐版本；
        # - 其他情况：直接 upgrade 到 head。
        eng = create_engine(settings.DATABASE_URL)
        try:
            insp = inspect(eng)
            has_ver = insp.has_table("alembic_version")
            has_users = insp.has_table("users")
        except Exception:
            has_ver = False
            has_users = False

        if not has_ver:
            if not has_users:
                # 空库：执行迁移全量建表
                command.upgrade(cfg, "head")
            else:
                # 既有表但无版本：与现状对齐
                command.stamp(cfg, "head")
        else:
            try:
                command.upgrade(cfg, "head")
            except Exception:
                # 兼容已存在相同列/索引导致的失败：直接以当前结构为准进行 stamp
                command.stamp(cfg, "head")
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("alembic upgrade 失败：%s", exc)


@app.on_event("startup")
def on_startup():
    # 1) 迁移策略：优先使用 Alembic 全量管理
    if getattr(settings, "USE_ALEMBIC_ONLY", True):
        _run_alembic_upgrade_head()
    else:
        # 兼容旧逻辑：先 ORM 自动建表，再 Alembic 升级
        ensure_database_schema()
        _run_alembic_upgrade_head()
    # 3) 引导默认数据
    bootstrap_defaults()
    # 4) 迁移执行可能修改了 logging（alembic.ini），此处重新校准日志到控制台+文件
    _configure_logging()
    logging.getLogger("allyend.boot").info(
        "应用启动完成，日志系统就绪（APP_ACCESS_LOG=%s）",
        _enable_app_access_log,
    )


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
app.include_router(configs_router.router)
app.include_router(configs_router.public_router)


# 便于 uv run 直接引用
# - 返回 ASGI 包裹器（若启用访问日志兜底），否则返回原生 FastAPI 实例
_asgi_app = _AccessLogASGI(app) if _enable_app_access_log in {"1", "true", "yes", "on"} else app

def get_app():
    return _asgi_app
