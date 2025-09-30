"""
Alembic 环境配置
- 目标：使用 app.models.Base.metadata 作为元数据；优先读取环境变量/应用配置中的 DATABASE_URL，兼容 alembic.ini。
- 兼容 SQLite（batch 模式）、PostgreSQL、MySQL/MariaDB。
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 读取 alembic.ini 配置
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def _get_url() -> str:
    # 1) 环境变量优先
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    # 2) 应用配置
    try:
        from app.config import settings  # noqa: WPS433

        if getattr(settings, "DATABASE_URL", None):
            return str(settings.DATABASE_URL)
    except Exception:
        # 忽略导入失败，回退到 alembic.ini
        pass
    # 3) alembic.ini
    return config.get_main_option("sqlalchemy.url")


# 目标元数据（用于 autogenerate）
from app.models import Base  # noqa: E402, WPS433

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=(connection.dialect.name == "sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

