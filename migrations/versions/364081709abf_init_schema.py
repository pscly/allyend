"""
初始化数据库结构（首个迁移）

说明：
- 本迁移用于“从空库”时一次性创建所有表结构，来源于 app.models 的 ORM 定义；
- 后续所有结构变更均通过增量迁移迭代，禁止再依赖 ORM 的 create_all；
- 允许 SQLite / PostgreSQL / MySQL(MariaDB)。

注意：
- 降级会直接 drop_all，开发环境可用；生产不建议执行降级。
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "364081709abf"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:  # noqa: D401
    """创建所有模型对应的表结构与索引/约束。"""
    # 说明：为确保与模型定义一致，这里直接基于 ORM 元数据创建。
    # 这是唯一一次允许在迁移中使用 ORM create_all 的场景（init 迁移）。
    bind = op.get_bind()
    from app.models import Base  # 延迟导入以避免循环引用

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:  # noqa: D401
    """删除所有由本项目创建的表（开发环境）。"""
    bind = op.get_bind()
    from app.models import Base  # 延迟导入以避免循环引用

    # 警告：这会删除所有表！仅用于开发或本地测试。
    Base.metadata.drop_all(bind=bind)

