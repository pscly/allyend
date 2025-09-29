"""
数据库初始化
- 使用 SQLAlchemy 2.0 风格
- 默认 SQLite（开发环境），生产可切换 MySQL/PostgreSQL
- 包含基础数据的自举逻辑
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from .config import settings
from .constants import (
    DEFAULT_GROUP_BLUEPRINTS,
    FILE_STORAGE_DIR,
    LOG_LEVEL_NAME_TO_CODE,
    ROLE_SUPERADMIN,
    ROLE_ADMIN,
    ROLE_USER,
)


class Base(DeclarativeBase):
    """ORM 基类"""


def _ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite"):
        db_path = url.replace("sqlite:///", "")
        _ensure_dir(Path(db_path).parent.as_posix())


_ensure_sqlite_dir(settings.DATABASE_URL)
_ensure_dir(settings.FILE_STORAGE_DIR or FILE_STORAGE_DIR)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def ensure_database_schema() -> None:
    """确保数据库结构就绪（无迁移版本，直接按 ORM 创建）。

    - 初始开发阶段：直接调用 Base.metadata.create_all(engine)
    - 若后续引入迁移，可替换为 Alembic 升级逻辑
    """
    # 延迟导入，避免循环
    from .models import Base as ModelsBase  # noqa: WPS433

    try:
        ModelsBase.metadata.create_all(bind=engine)
    except Exception:
        # 尽量不要阻断启动；将错误留给上层日志
        raise
    # 轻量列升级：为现有库补齐新增列（设备名）
    try:
        _ensure_extra_columns()
    except Exception:
        # 忽略升级失败，避免影响启动；建议通过迁移工具修复
        pass


## 兼容层 apply_schema_upgrades 已移除：初期不再使用 Alembic 迁移


def bootstrap_defaults() -> None:
    """初始化默认数据：用户组、超级管理员、默认邀请码等。"""

    from .models import (
        InviteCode,
        User,
        UserGroup,
    )
    from .auth import get_password_hash

    with SessionLocal() as session:  # type: Session
        # 1. 确认用户组
        default_group: Optional[UserGroup] = None
        admin_group: Optional[UserGroup] = None
        for blueprint in DEFAULT_GROUP_BLUEPRINTS:
            group = session.query(UserGroup).filter(UserGroup.slug == blueprint["slug"]).first()
            if not group:
                group = UserGroup(
                    name=blueprint["name"],
                    slug=blueprint["slug"],
                    description=blueprint.get("description"),
                    is_default=blueprint.get("is_default", False),
                    enable_crawlers=blueprint.get("enable_crawlers", True),
                    enable_files=blueprint.get("enable_files", True),
                )
                session.add(group)
            else:
                group.description = blueprint.get("description")
                group.is_default = blueprint.get("is_default", group.is_default)
                group.enable_crawlers = blueprint.get("enable_crawlers", group.enable_crawlers)
                group.enable_files = blueprint.get("enable_files", group.enable_files)

            if blueprint.get("is_default"):
                default_group = group
            if blueprint["slug"] == "admins":
                admin_group = group
        session.flush()

        if default_group is None:
            default_group = session.query(UserGroup).order_by(UserGroup.id).first()
        if admin_group is None:
            admin_group = default_group

        # 2. 超级管理员
        root_username = settings.ROOT_ADMIN_USERNAME
        root_user = session.query(User).filter(User.username == root_username).first()
        if not root_user:
            password_source = settings.ROOT_ADMIN_PASSWORD or settings.SECRET_KEY
            root_user = User(
                username=root_username,
                hashed_password=get_password_hash(password_source),
                display_name=root_username,
                role=ROLE_SUPERADMIN,
                is_root_admin=True,
                is_active=True,
            )
            root_user.group = admin_group
            session.add(root_user)
        else:
            if root_user.role != ROLE_SUPERADMIN:
                root_user.role = ROLE_SUPERADMIN
            if not root_user.is_root_admin:
                root_user.is_root_admin = True
            if root_user.group_id is None:
                root_user.group = admin_group
            if not root_user.display_name:
                root_user.display_name = root_user.username
        session.flush()

        # 3. 默认邀请码
        def ensure_invite(code: Optional[str], allow_admin: bool, group: UserGroup, note: str) -> None:
            if not code:
                return
            invite = session.query(InviteCode).filter(InviteCode.code == code).first()
            if not invite:
                invite = InviteCode(
                    code=code,
                    allow_admin=allow_admin,
                    target_group=group,
                    note=note,
                    creator=root_user,
                    max_uses=None,
                )
                session.add(invite)
            else:
                invite.allow_admin = allow_admin
                invite.target_group = group
                invite.note = note

        ensure_invite(settings.ROOT_ADMIN_INVITE_CODE, True, admin_group, "超级管理员专用邀请码")
        ensure_invite(settings.DEFAULT_ADMIN_INVITE_CODE, True, admin_group, "管理员默认邀请码")
        ensure_invite(settings.DEFAULT_USER_INVITE_CODE, False, default_group, "普通用户默认邀请码")

        session.commit()


__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "ensure_database_schema",
    "bootstrap_defaults",
]


def _ensure_extra_columns() -> None:
    """在无迁移场景下，按需补齐新增字段。

    - log_entries.device_name VARCHAR(128)
    - crawler_heartbeats.device_name VARCHAR(128)
    - c r a w l e r s .last_device_name VARCHAR(128)
    """
    from sqlalchemy import inspect

    insp = inspect(engine)
    dialect = engine.dialect.name

    def has_col(table: str, column: str) -> bool:
        try:
            cols = [c['name'] if isinstance(c, dict) else getattr(c, 'name', None) for c in insp.get_columns(table)]
            return column in cols
        except Exception:
            return False

    def add_col(table: str, ddl: str) -> None:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))

    # SQLite/MySQL/PostgreSQL 统一使用简单 DDL（兼容性较好）
    if not has_col('log_entries', 'device_name'):
        add_col('log_entries', 'device_name VARCHAR(128)')
    if not has_col('crawler_heartbeats', 'device_name'):
        add_col('crawler_heartbeats', 'device_name VARCHAR(128)')
    if not has_col('crawlers', 'last_device_name'):
        add_col('crawlers', 'last_device_name VARCHAR(128)')
    # 新增爬虫置顶时间列
    if not has_col('crawlers', 'pinned_at'):
        add_col('crawlers', 'pinned_at DATETIME')

