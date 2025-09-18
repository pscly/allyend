"""
数据库初始化
- 使用 SQLAlchemy 2.0 风格
- 默认 SQLite（开发环境），生产可切换 MySQL/PostgreSQL
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings


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

