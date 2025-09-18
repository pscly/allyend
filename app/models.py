"""
ORM 模型定义
- 用户、API Key、爬虫、运行、日志
- 分组、邀请码、文件存储等扩展能力
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class UserGroup(Base):
    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    enable_crawlers: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_files: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users: Mapped[List["User"]] = relationship("User", back_populates="group")


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    allow_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    creator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    creator: Mapped[Optional["User"]] = relationship("User", back_populates="invite_codes_created", foreign_keys=[creator_id])

    target_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user_groups.id"), nullable=True)
    target_group: Mapped[Optional[UserGroup]] = relationship("UserGroup")

    usages: Mapped[List["InviteUsage"]] = relationship("InviteUsage", back_populates="invite", cascade="all, delete-orphan")


class InviteUsage(Base):
    __tablename__ = "invite_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    invite_id: Mapped[int] = mapped_column(ForeignKey("invite_codes.id"))
    invite: Mapped[InviteCode] = relationship("InviteCode", back_populates="usages")

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship("User", back_populates="invite_usage")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(32), default="user")  # user/admin/superadmin
    is_root_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    theme_name: Mapped[str] = mapped_column(String(32), default="classic")
    theme_primary: Mapped[str] = mapped_column(String(16), default="#10b981")
    theme_secondary: Mapped[str] = mapped_column(String(16), default="#1f2937")
    theme_background: Mapped[str] = mapped_column(String(16), default="#f9fafb")
    is_dark_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user_groups.id"), nullable=True)
    group: Mapped[Optional[UserGroup]] = relationship("UserGroup", back_populates="users")

    invited_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    invited_by: Mapped[Optional["User"]] = relationship("User", remote_side=[id], back_populates="invited_users", foreign_keys=[invited_by_id])
    invited_users: Mapped[List["User"]] = relationship("User", back_populates="invited_by", foreign_keys=[invited_by_id])

    invite_code_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invite_codes.id"), nullable=True)
    invite_code: Mapped[Optional[InviteCode]] = relationship("InviteCode")

    invite_codes_created: Mapped[List[InviteCode]] = relationship("InviteCode", back_populates="creator", foreign_keys=[InviteCode.creator_id])
    invite_usage: Mapped[Optional[InviteUsage]] = relationship("InviteUsage", back_populates="user", uselist=False)

    api_keys: Mapped[List["APIKey"]] = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    crawlers: Mapped[List["Crawler"]] = relationship("Crawler", back_populates="user", cascade="all, delete-orphan")
    file_tokens: Mapped[List["FileAPIToken"]] = relationship("FileAPIToken", back_populates="user", cascade="all, delete-orphan")
    files_owned: Mapped[List["FileEntry"]] = relationship("FileEntry", back_populates="owner", cascade="all, delete-orphan", foreign_keys="FileEntry.owner_id")


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)  # 简化起见明文存储（生产建议哈希）
    name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship("User", back_populates="api_keys")

    quick_links: Mapped[List["CrawlerAccessLink"]] = relationship("CrawlerAccessLink", back_populates="api_key")
    logs: Mapped[List["LogEntry"]] = relationship("LogEntry", back_populates="api_key")


class Crawler(Base):
    __tablename__ = "crawlers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_source_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    public_slug: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship("User", back_populates="crawlers")

    runs: Mapped[List["CrawlerRun"]] = relationship("CrawlerRun", back_populates="crawler", cascade="all, delete-orphan")
    logs: Mapped[List["LogEntry"]] = relationship("LogEntry", back_populates="crawler", cascade="all, delete-orphan")
    quick_links: Mapped[List["CrawlerAccessLink"]] = relationship("CrawlerAccessLink", back_populates="crawler")


class CrawlerRun(Base):
    __tablename__ = "crawler_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running/success/failed
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

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
    source_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    crawler_id: Mapped[int] = mapped_column(ForeignKey("crawlers.id"))
    crawler: Mapped[Crawler] = relationship("Crawler", back_populates="logs")

    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("crawler_runs.id"), nullable=True)
    run: Mapped[Optional[CrawlerRun]] = relationship("CrawlerRun", back_populates="logs")

    api_key_id: Mapped[Optional[int]] = mapped_column(ForeignKey("api_keys.id"), nullable=True)
    api_key: Mapped[Optional[APIKey]] = relationship("APIKey", back_populates="logs")


class CrawlerAccessLink(Base):
    __tablename__ = "crawler_access_links"
    __table_args__ = (UniqueConstraint("slug", name="uq_crawler_access_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    target_type: Mapped[str] = mapped_column(String(16))  # crawler / api_key
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_logs: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    crawler_id: Mapped[Optional[int]] = mapped_column(ForeignKey("crawlers.id"), nullable=True)
    crawler: Mapped[Optional[Crawler]] = relationship("Crawler", back_populates="quick_links")

    api_key_id: Mapped[Optional[int]] = mapped_column(ForeignKey("api_keys.id"), nullable=True)
    api_key: Mapped[Optional[APIKey]] = relationship("APIKey", back_populates="quick_links")

    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[Optional[User]] = relationship("User")


class FileAPIToken(Base):
    __tablename__ = "file_api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_ips: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    allowed_cidrs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped[User] = relationship("User", back_populates="file_tokens")

    uploads: Mapped[List["FileEntry"]] = relationship("FileEntry", back_populates="uploaded_by_token")
    logs: Mapped[List["FileAccessLog"]] = relationship("FileAccessLog", back_populates="token")


class FileEntry(Base):
    __tablename__ = "file_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_path: Mapped[str] = mapped_column(String(255), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="private")  # private/group/public
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    download_count: Mapped[int] = mapped_column(Integer, default=0)

    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    owner: Mapped[Optional[User]] = relationship("User", back_populates="files_owned", foreign_keys=[owner_id])

    owner_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user_groups.id"), nullable=True)
    owner_group: Mapped[Optional[UserGroup]] = relationship("UserGroup")

    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_by_user: Mapped[Optional[User]] = relationship("User", foreign_keys=[uploaded_by_user_id])

    uploaded_by_token_id: Mapped[Optional[int]] = mapped_column(ForeignKey("file_api_tokens.id"), nullable=True)
    uploaded_by_token: Mapped[Optional[FileAPIToken]] = relationship("FileAPIToken", back_populates="uploads")

    access_logs: Mapped[List["FileAccessLog"]] = relationship("FileAccessLog", back_populates="file", cascade="all, delete-orphan")


class FileAccessLog(Base):
    __tablename__ = "file_access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(32))  # upload/download/delete/list
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("file_entries.id"), nullable=True)
    file: Mapped[Optional[FileEntry]] = relationship("FileEntry", back_populates="access_logs")

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    user: Mapped[Optional[User]] = relationship("User")

    token_id: Mapped[Optional[int]] = mapped_column(ForeignKey("file_api_tokens.id"), nullable=True)
    token: Mapped[Optional[FileAPIToken]] = relationship("FileAPIToken", back_populates="logs")

