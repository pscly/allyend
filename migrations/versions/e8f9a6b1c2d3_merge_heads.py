"""merge heads a1b2c3d4e5f6 and d3a4b1f6e781

用于合并分叉的迁移分支，保持单一 head。

Revision ID: e8f9a6b1c2d3
Revises: a1b2c3d4e5f6, d3a4b1f6e781
Create Date: 2025-09-22 17:07:00
"""
from __future__ import annotations

# Alembic identifiers
revision = "e8f9a6b1c2d3"
down_revision = ("a1b2c3d4e5f6", "d3a4b1f6e781")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 纯合并迁移，无实际 DDL 操作
    pass


def downgrade() -> None:
    # 合并迁移通常不执行回退
    pass

