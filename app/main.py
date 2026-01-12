"""
应用入口：
- FastAPI 初始化、模板/静态资源、路由挂载
- 启动时执行 Alembic 迁移与数据自检
"""
from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from .config import settings
from .database import bootstrap_defaults, ensure_database_schema, engine
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


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # 测试环境（pytest）下不做自动迁移/自举，避免污染本地 data/app.db 并影响用例隔离
    if os.getenv("PYTEST_CURRENT_TEST") or "pytest" in sys.modules:
        logging.getLogger("allyend.boot").info("检测到 pytest 环境，跳过启动迁移与默认数据自举")
        yield
        return

    # 1) 迁移策略：优先使用 Alembic 全量管理
    if getattr(settings, "USE_ALEMBIC_ONLY", True):
        _run_alembic_upgrade_head()
    else:
        # 兼容旧逻辑：先 ORM 自动建表，再 Alembic 升级
        ensure_database_schema()
        _run_alembic_upgrade_head()

    # 2) 引导默认数据
    bootstrap_defaults()

    # 3) 迁移执行可能修改了 logging（alembic.ini），此处重新校准日志到控制台+文件
    _configure_logging()
    logging.getLogger("allyend.boot").info(
        "应用启动完成，日志系统就绪（APP_ACCESS_LOG=%s）",
        _enable_app_access_log,
    )

    yield


app = FastAPI(title=settings.SITE_NAME, version="0.2.0", lifespan=lifespan)

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
_AVATAR_DIR = Path(settings.FILE_STORAGE_DIR or "data/files").resolve() / "avatars"
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
    """启动时执行 Alembic 迁移/校准（保守兜底）。

    默认行为：
    - 执行 `alembic upgrade head`，将数据库迁移到最新版本。

    兜底策略（仅在“比较确定”的情况下才会 stamp）：
    - 若升级失败且检测到“历史库”（无 `alembic_version` 但存在 `users`），执行 `stamp head`；
    - 若升级失败且检测到“版本链异常”（当前 revision 在迁移文件中不存在），执行 `stamp head`。

    无法确认安全时：直接抛出异常，避免在未知状态下继续启动。
    """
    from alembic import command  # type: ignore
    from alembic.config import Config  # type: ignore
    from sqlalchemy import inspect

    logger = logging.getLogger(__name__)
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    # 使用 app 配置覆盖 alembic.ini，保证本地与容器一致
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    try:
        command.upgrade(cfg, "head")
        return
    except Exception as exc:  # noqa: BLE001
        # 读取当前库表结构信息（用于判断是否为“历史库”/是否具备版本表）
        try:
            tables = set(inspect(engine).get_table_names())
        except Exception:  # noqa: BLE001
            tables = set()

        has_version_table = "alembic_version" in tables
        has_core_tables = "users" in tables

        # 兜底 1：无 alembic_version 但已有核心业务表
        # 典型场景：早期版本通过 ORM create_all/手工建表，后续引入 Alembic。
        if (not has_version_table) and has_core_tables:
            logger.warning(
                "alembic upgrade 失败，检测到历史库（无 alembic_version 且存在 users），将执行 stamp head：%s",
                exc,
            )
            command.stamp(cfg, "head")
            return

        # 兜底 2：版本链异常（当前版本号指向不存在的 revision）
        # 典型场景：迁移文件被清理/缺失，导致无法从现有 revision 继续 upgrade。
        missing_revision_markers = (
            "Can't locate revision identified by",
            "No such revision or branch",
        )
        if has_version_table and any(marker in str(exc) for marker in missing_revision_markers):
            logger.warning(
                "alembic upgrade 失败，检测到版本链异常，将执行 stamp head 以对齐版本号：%s",
                exc,
            )
            command.stamp(cfg, "head")
            return

        logger.exception("alembic upgrade 失败，拒绝自动 stamp：%s", exc)
        raise




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
