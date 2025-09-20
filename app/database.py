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
from alembic import command
from alembic.config import Config

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


def _build_alembic_config() -> Config:
    """构建 Alembic 配置指向当前项目。"""
    project_root = Path(__file__).resolve().parent.parent
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return config


def ensure_database_schema(target: str = "head") -> None:
    """确保数据库迁移已经应用，兼容旧版本无版本表的场景。"""
    inspector = inspect(engine)
    has_version_table = inspector.has_table("alembic_version")
    alembic_config = _build_alembic_config()

    if not has_version_table:
        existing_tables = [name for name in inspector.get_table_names() if name != "alembic_version"]
        if existing_tables:
            command.stamp(alembic_config, target)
            return
    command.upgrade(alembic_config, target)


def apply_schema_upgrades() -> None:
    """确保新增列存在并对旧数据进行补齐。"""

    def ensure(table: str, column: str, ddl: str) -> bool:
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns(table)}
        if column not in columns:
            column_ddl = ddl.strip()
            if not column_ddl.lower().startswith(column.lower() + " "):
                column_ddl = f"{column} {column_ddl}"
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_ddl}"))
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

    # user 主题字段（旧版本兼容）
    ensure("users", "theme_name", "VARCHAR(32) DEFAULT 'classic'")
    ensure("users", "theme_primary", "VARCHAR(16) DEFAULT '#10b981'")
    ensure("users", "theme_secondary", "VARCHAR(16) DEFAULT '#1f2937'")
    ensure("users", "theme_background", "VARCHAR(16) DEFAULT '#f9fafb'")
    ensure("users", "is_dark_mode", "BOOLEAN DEFAULT 0")
    ensure("users", "display_name", "VARCHAR(128)")
    ensure("users", "email", "VARCHAR(128)")

    # 新增权限相关字段
    ensure("users", "role", "VARCHAR(32) DEFAULT 'user'")
    ensure("users", "is_root_admin", "BOOLEAN DEFAULT 0")
    ensure("users", "group_id", "INTEGER")
    ensure("users", "invited_by_id", "INTEGER")
    ensure("users", "invite_code_id", "INTEGER")

    # API Key 扩展
    ensure("api_keys", "name", "VARCHAR(64)")
    ensure("api_keys", "description", "TEXT")
    ensure("api_keys", "last_used_at", "DATETIME")
    ensure("api_keys", "last_used_ip", "VARCHAR(64)")
    ensure("api_keys", "is_public", "BOOLEAN DEFAULT 0")
    api_key_local_added = ensure("api_keys", "local_id", "INTEGER")

    # 爬虫与运行扩展
    ensure("crawlers", "is_public", "BOOLEAN DEFAULT 0")
    ensure("crawlers", "public_slug", "VARCHAR(64)")
    ensure("crawlers", "last_source_ip", "VARCHAR(64)")
    crawler_local_added = ensure("crawlers", "local_id", "INTEGER")
    ensure("crawler_runs", "source_ip", "VARCHAR(64)")

    with engine.begin() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_api_keys_user_local ON api_keys(user_id, local_id)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_crawlers_user_local ON crawlers(user_id, local_id)"))

    needs_backfill = api_key_local_added or crawler_local_added
    if not needs_backfill:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT COUNT(1) FROM api_keys WHERE local_id IS NULL"))
            needs_backfill = needs_backfill or result.scalar_one() > 0
            result = conn.execute(text("SELECT COUNT(1) FROM crawlers WHERE local_id IS NULL"))
            needs_backfill = needs_backfill or result.scalar_one() > 0

    if needs_backfill:
        from .models import APIKey, Crawler

        with SessionLocal() as session:
            def _assign_local_ids(model):
                changed = False
                counters = {}
                rows = (
                    session.query(model)
                    .order_by(model.user_id, model.created_at, model.id)
                    .all()
                )
                for row in rows:
                    current = counters.get(row.user_id, 0)
                    if row.local_id and row.local_id > 0:
                        counters[row.user_id] = max(current, row.local_id)
                        continue
                    next_value = current + 1
                    row.local_id = next_value
                    counters[row.user_id] = next_value
                    changed = True
                return changed

            changed = False
            changed = _assign_local_ids(APIKey) or changed
            changed = _assign_local_ids(Crawler) or changed
            if changed:
                session.commit()
            else:
                session.rollback()

    # 日志来源
    ensure("crawlers", "is_public", "BOOLEAN DEFAULT 0")
    ensure("crawlers", "public_slug", "VARCHAR(64)")
    ensure("crawlers", "last_source_ip", "VARCHAR(64)")
    ensure("crawler_runs", "source_ip", "VARCHAR(64)")

    # 日志来源
    ensure("log_entries", "source_ip", "VARCHAR(64)")
    ensure("log_entries", "api_key_id", "INTEGER")


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
    "apply_schema_upgrades",
    "bootstrap_defaults",
]

