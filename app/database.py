"""
数据库初始化
- 使用 SQLAlchemy 2.0 风格
- 默认 SQLite（开发环境），生产可切换 MySQL/PostgreSQL
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings
from .constants import LOG_LEVEL_NAME_TO_CODE


class Base(DeclarativeBase):
    """ORM 基类"""


def _ensure_sqlite_dir(url: str) -> None:
    """若使用 SQLite，确保 data 目录存在。"""
    if url.startswith("sqlite"):
        # 形如 sqlite:///./data/app.db
        db_path = url.replace("sqlite:///", "")
        db_file = Path(db_path)
        if db_file.parent and not db_file.parent.exists():
            db_file.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.DATABASE_URL)

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {})

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)




def apply_schema_upgrades() -> None:
    """确保新增列存在并对旧数据进行补齐。"""

    def ensure(table: str, column: str, ddl: str) -> bool:
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns(table)}
        if column not in columns:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
            return True
        return False

    added_level_code = ensure("log_entries", "level_code", "INTEGER DEFAULT 20")
    if added_level_code:
        with engine.begin() as conn:
            for name, code in LOG_LEVEL_NAME_TO_CODE.items():
                conn.execute(
                    text("UPDATE log_entries SET level_code = :code WHERE level = :name"),
                    {"code": code, "name": name},
                )
            conn.execute(text("UPDATE log_entries SET level_code = 20 WHERE level_code IS NULL"))

    ensure("api_keys", "is_public", "BOOLEAN DEFAULT 0")
    ensure("crawlers", "is_public", "BOOLEAN DEFAULT 0")
    ensure("crawlers", "public_slug", "VARCHAR(64)")
    ensure("users", "theme_name", "VARCHAR(32) DEFAULT 'classic'")
    ensure("users", "theme_primary", "VARCHAR(16) DEFAULT '#10b981'")
    ensure("users", "theme_secondary", "VARCHAR(16) DEFAULT '#1f2937'")
    ensure("users", "theme_background", "VARCHAR(16) DEFAULT '#f9fafb'")
    ensure("users", "is_dark_mode", "BOOLEAN DEFAULT 0")


