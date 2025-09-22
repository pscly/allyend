"""add crawler_heartbeats and crawler_commands tables

Revision ID: c1d2e3f4a5b6
Revises: b7d2e1f3a9c0
Create Date: 2025-09-22 18:20:00

说明
- 新增与 ORM 模型一致的表：crawler_heartbeats、crawler_commands。
- 仅当表不存在时创建，保证幂等。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "b7d2e1f3a9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())

    if "crawler_heartbeats" not in existing_tables:
        op.create_table(
            "crawler_heartbeats",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("source_ip", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("crawler_id", sa.Integer(), sa.ForeignKey("crawlers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("api_key_id", sa.Integer(), sa.ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_crawler_heartbeats_created_at", "crawler_heartbeats", ["created_at"])  # 查询优化

    if "crawler_commands" not in existing_tables:
        op.create_table(
            "crawler_commands",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("command", sa.String(length=32), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("crawler_id", sa.Integer(), sa.ForeignKey("crawlers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("issued_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())
    if "crawler_commands" in existing_tables:
        op.drop_table("crawler_commands")
    if "crawler_heartbeats" in existing_tables:
        try:
            op.drop_index("ix_crawler_heartbeats_created_at", table_name="crawler_heartbeats")
        except Exception:
            pass
        op.drop_table("crawler_heartbeats")

