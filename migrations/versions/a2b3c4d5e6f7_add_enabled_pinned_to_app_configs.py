"""为 app_configs 增加 enabled 与 pinned_at 字段

Revision ID: a2b3c4d5e6f7
Revises: c9a1b6d7e8f0
Create Date: 2025-10-13 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "c9a1b6d7e8f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    dialect = bind.dialect.name
    # 不同数据库的布尔默认值写法不同
    if dialect == "postgresql":
        bool_true = sa.text("TRUE")
    else:
        # sqlite / mysql(mariadb)
        bool_true = sa.text("1")

    # 兼容多数据库：仅当列不存在时添加
    cols = {c["name"] for c in insp.get_columns("app_configs")}
    if "enabled" not in cols:
        op.add_column("app_configs", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=bool_true))
    if "pinned_at" not in cols:
        op.add_column("app_configs", sa.Column("pinned_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # 可逆删除列（部分数据库可能需要注意默认值/索引）
    with op.batch_alter_table("app_configs") as batch_op:
        try:
            batch_op.drop_column("pinned_at")
        except Exception:
            pass
        try:
            batch_op.drop_column("enabled")
        except Exception:
            pass
