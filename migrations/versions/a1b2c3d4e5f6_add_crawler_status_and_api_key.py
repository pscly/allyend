"""add crawler status fields and api_key link

Revision ID: a1b2c3d4e5f6
Revises: 9f2a0c4b9e3a
Create Date: 2025-09-22 16:30:00

变更内容
- 为 crawlers 表补齐缺失的列：status、status_changed_at、uptime_ratio、uptime_minutes、heartbeat_payload
- 新增 crawlers.api_key_id 外键并添加唯一约束（一个 API Key 仅绑定一个爬虫）

兼容性说明
- 仅在目标列缺失时添加，幂等安全；SQLite 使用 batch 模式。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "6a1f2c9d3b0a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    existing_columns = {c["name"] for c in inspector.get_columns("crawlers")}

    # 需要添加的列定义
    add_cols: list[tuple[str, sa.Column]] = []
    if "status" not in existing_columns:
        add_cols.append(("status", sa.Column("status", sa.String(length=16), nullable=False, server_default="offline")))
    if "status_changed_at" not in existing_columns:
        add_cols.append(("status_changed_at", sa.Column("status_changed_at", sa.DateTime(), nullable=True)))
    if "uptime_ratio" not in existing_columns:
        add_cols.append(("uptime_ratio", sa.Column("uptime_ratio", sa.Float(), nullable=True)))
    if "uptime_minutes" not in existing_columns:
        add_cols.append(("uptime_minutes", sa.Column("uptime_minutes", sa.Float(), nullable=True)))
    if "heartbeat_payload" not in existing_columns:
        add_cols.append(("heartbeat_payload", sa.Column("heartbeat_payload", sa.JSON(), nullable=True)))

    # 先批量添加简单列
    if dialect == "sqlite":
        with op.batch_alter_table("crawlers") as batch_op:
            for _, col in add_cols:
                batch_op.add_column(col)
    else:
        for _, col in add_cols:
            op.add_column("crawlers", col)

    # 处理 api_key_id 外键与唯一约束
    # - 优先添加列
    # - 再创建唯一约束（若不存在）与外键（若不存在）
    existing_columns = {c["name"] for c in inspector.get_columns("crawlers")}
    fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("crawlers")}

    if dialect == "sqlite":
        with op.batch_alter_table("crawlers") as batch_op:
            if "api_key_id" not in existing_columns:
                batch_op.add_column(sa.Column("api_key_id", sa.Integer(), nullable=True))
            # 创建唯一约束（若不存在）
            # SQLite 下 batch 模式会重建表结构，名称冲突概率低；做存在性保护
            try:
                batch_op.create_unique_constraint("uq_crawlers_api_key_id", ["api_key_id"])
            except Exception:
                pass
            if "fk_crawlers_api_key_id" not in fk_names:
                batch_op.create_foreign_key(
                    "fk_crawlers_api_key_id",
                    "api_keys",
                    ["api_key_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
    else:
        if "api_key_id" not in existing_columns:
            op.add_column("crawlers", sa.Column("api_key_id", sa.Integer(), nullable=True))
        # 唯一约束
        try:
            op.create_unique_constraint("uq_crawlers_api_key_id", "crawlers", ["api_key_id"])
        except Exception:
            pass
        if "fk_crawlers_api_key_id" not in fk_names:
            op.create_foreign_key(
                "fk_crawlers_api_key_id",
                "crawlers",
                "api_keys",
                ["api_key_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    # 降级时尽力删除外键/唯一约束与列（存在性判断）
    if dialect == "sqlite":
        with op.batch_alter_table("crawlers") as batch_op:
            fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("crawlers")}
            if "fk_crawlers_api_key_id" in fk_names:
                batch_op.drop_constraint("fk_crawlers_api_key_id", type_="foreignkey")
            # 唯一约束名称删除时可能抛错，忽略
            try:
                batch_op.drop_constraint("uq_crawlers_api_key_id", type_="unique")
            except Exception:
                pass
            cols = {c["name"] for c in inspector.get_columns("crawlers")}
            for name in ["api_key_id", "heartbeat_payload", "uptime_minutes", "uptime_ratio", "status_changed_at", "status"]:
                if name in cols:
                    batch_op.drop_column(name)
    else:
        fks = {fk.get("name") for fk in inspector.get_foreign_keys("crawlers")}
        if "fk_crawlers_api_key_id" in fks:
            op.drop_constraint("fk_crawlers_api_key_id", "crawlers", type_="foreignkey")
        try:
            op.drop_constraint("uq_crawlers_api_key_id", "crawlers", type_="unique")
        except Exception:
            pass
        cols = {c["name"] for c in inspector.get_columns("crawlers")}
        for name in ["api_key_id", "heartbeat_payload", "uptime_minutes", "uptime_ratio", "status_changed_at", "status"]:
            if name in cols:
                op.drop_column("crawlers", name)
