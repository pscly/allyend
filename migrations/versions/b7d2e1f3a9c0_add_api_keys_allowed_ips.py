"""add allowed_ips column to api_keys

为 api_keys 表新增 allowed_ips 列，以匹配当前 ORM 模型定义。

Revision ID: b7d2e1f3a9c0
Revises: d3a4b1f6e781
Create Date: 2025-09-22 17:05:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7d2e1f3a9c0"
down_revision = "e8f9a6b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """在缺失时添加 api_keys.allowed_ips 列（SQLite 使用 batch 模式）。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    columns = {c["name"] for c in inspector.get_columns("api_keys")}
    if "allowed_ips" in columns:
        return

    col = sa.Column("allowed_ips", sa.Text(), nullable=True)

    if dialect == "sqlite":
        with op.batch_alter_table("api_keys") as batch_op:
            batch_op.add_column(col)
    else:
        op.add_column("api_keys", col)


def downgrade() -> None:
    """回滚时删除 allowed_ips 列（存在性保护）。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    columns = {c["name"] for c in inspector.get_columns("api_keys")}
    if "allowed_ips" not in columns:
        return

    if dialect == "sqlite":
        with op.batch_alter_table("api_keys") as batch_op:
            batch_op.drop_column("allowed_ips")
    else:
        op.drop_column("api_keys", "allowed_ips")
