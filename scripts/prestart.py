"""
容器启动前置脚本：等待数据库并自动迁移（Alembic）

特性：
- 读取环境变量/应用配置的 DATABASE_URL；
- 等待数据库就绪（重试）；
- 运行 Alembic upgrade head；
- 对 SQLite 仍调用 ensure_database_schema 以做轻量补齐（包含历史兜底）。

编码：UTF-8（无 BOM）
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

from sqlalchemy import create_engine, text


def get_database_url() -> str:
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    try:
        from app.config import settings  # type: ignore

        if getattr(settings, "DATABASE_URL", None):
            return str(settings.DATABASE_URL)
    except Exception:
        pass
    # 最后回退到 alembic.ini（由 env.py 处理），但此处最好明确返回一个 URL
    return "sqlite:///./data/app.db"


def wait_for_db(url: str, timeout: float = 60.0) -> None:
    deadline = time.time() + max(1.0, timeout)
    last_err: Optional[Exception] = None
    while time.time() < deadline:
        try:
            engine = create_engine(url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.0)
    if last_err:
        print(f"[prestart] 数据库等待超时：{last_err}", file=sys.stderr)
        # 不中断，交给应用报错更可见


def run_alembic(url: str) -> None:
    from alembic.config import Config  # type: ignore
    from alembic import command  # type: ignore

    cfg = Config("alembic.ini")
    # 覆盖 URL，优先环境/应用配置
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    print("[prestart] Alembic upgrade head 完成")


def main() -> None:
    url = get_database_url()
    print(f"[prestart] 使用数据库：{url}")
    wait_for_db(url, timeout=float(os.getenv("DB_WAIT_TIMEOUT", "60")))
    # 先创建/补齐基础结构，再执行迁移，保证初装 PG 也能成功
    try:
        from app.database import ensure_database_schema  # type: ignore

        ensure_database_schema()
        print("[prestart] ensure_database_schema 完成")
    except Exception as exc:  # noqa: BLE001
        print(f"[prestart] ensure_database_schema 失败：{exc}", file=sys.stderr)
    try:
        run_alembic(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[prestart] 迁移失败：{exc}", file=sys.stderr)
        # 不中断：交给应用启动时再暴露更详细错误


if __name__ == "__main__":
    main()
