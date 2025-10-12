"""新增 app 配置与读取日志表

Revision ID: c9a1b6d7e8f0
Revises: b1a2c3d4e5f6
Create Date: 2025-10-12 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9a1b6d7e8f0"
down_revision = "b1a2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_app_config_read_logs_created_at", table_name="app_config_read_logs")
    op.drop_index("ix_app_config_read_logs_app", table_name="app_config_read_logs")
    op.drop_table("app_config_read_logs")

    op.drop_index("ix_app_configs_app", table_name="app_configs")
    op.drop_table("app_configs")

