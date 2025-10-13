"""新增 app 配置与读取日志表

Revision ID: c9a1b6d7e8f0
Revises: b1a2c3d4e5f6
Create Date: 2025-10-12 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "c9a1b6d7e8f0"
down_revision = "b1a2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # app_configs 表与索引（若存在则跳过/补齐索引）
    if not insp.has_table("app_configs"):
        op.create_table(
            "app_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("app", sa.String(length=64), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("app", name="uq_app_configs_app"),
        )
        op.create_index("ix_app_configs_app", "app_configs", ["app"], unique=False)
    else:
        try:
            idx_names = {i.get("name") for i in insp.get_indexes("app_configs")}
        except Exception:
            idx_names = set()
        if "ix_app_configs_app" not in idx_names:
            op.create_index("ix_app_configs_app", "app_configs", ["app"], unique=False)

    # app_config_read_logs 表与索引
    if not insp.has_table("app_config_read_logs"):
        op.create_table(
            "app_config_read_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("app", sa.String(length=64), nullable=False),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_app_config_read_logs_app", "app_config_read_logs", ["app"], unique=False)
        op.create_index("ix_app_config_read_logs_created_at", "app_config_read_logs", ["created_at"], unique=False)
    else:
        try:
            idx_names = {i.get("name") for i in insp.get_indexes("app_config_read_logs")}
        except Exception:
            idx_names = set()
        if "ix_app_config_read_logs_app" not in idx_names:
            op.create_index("ix_app_config_read_logs_app", "app_config_read_logs", ["app"], unique=False)
        if "ix_app_config_read_logs_created_at" not in idx_names:
            op.create_index("ix_app_config_read_logs_created_at", "app_config_read_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_app_config_read_logs_created_at", table_name="app_config_read_logs")
    op.drop_index("ix_app_config_read_logs_app", table_name="app_config_read_logs")
    op.drop_table("app_config_read_logs")

    op.drop_index("ix_app_configs_app", table_name="app_configs")
    op.drop_table("app_configs")
