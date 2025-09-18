"""
ORM 模型定义
- 用户、API Key、爬虫、运行、日志
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    theme_name: Mapped[str] = mapped_column(String(32), default="classic")
    theme_primary: Mapped[str] = mapped_column(String(16), default="#10b981")
    theme_secondary: Mapped[str] = mapped_column(String(16), default="#1f2937")
    is_dark_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    api_keys: Mapped[List["APIKey"]] = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    crawlers: Mapped[List["Crawler"]] = relationship("Crawler", back_populates="user", cascade="all, delete-orphan")


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)  # 简化起见明文存储（生产建议哈希）
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship("User", back_populates="api_keys")


class Crawler(Base):
    __tablename__ = "crawlers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    public_slug: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship("User", back_populates="crawlers")

    runs: Mapped[List["CrawlerRun"]] = relationship("CrawlerRun", back_populates="crawler", cascade="all, delete-orphan")
    logs: Mapped[List["LogEntry"]] = relationship("LogEntry", back_populates="crawler", cascade="all, delete-orphan")


class CrawlerRun(Base):
    __tablename__ = "crawler_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running/success/failed
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    crawler_id: Mapped[int] = mapped_column(ForeignKey("crawlers.id"))
    crawler: Mapped[Crawler] = relationship("Crawler", back_populates="runs")

    logs: Mapped[List["LogEntry"]] = relationship("LogEntry", back_populates="run", cascade="all, delete-orphan")


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    level_code: Mapped[int] = mapped_column(Integer, default=20, index=True)
    message: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    crawler_id: Mapped[int] = mapped_column(ForeignKey("crawlers.id"))
    crawler: Mapped[Crawler] = relationship("Crawler", back_populates="logs")

    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("crawler_runs.id"), nullable=True)
    run: Mapped[Optional[CrawlerRun]] = relationship("CrawlerRun", back_populates="logs")






