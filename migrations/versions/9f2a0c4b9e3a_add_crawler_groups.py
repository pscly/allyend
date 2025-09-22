"""add crawler_groups table and link api_keys/crawlers

Revision ID: 9f2a0c4b9e3a
Revises: 364081709abf
Create Date: 2025-09-22 14:05:00

变更内容
- 新增 crawler_groups 表（用户下的爬虫分组）
- 为 api_keys 与 crawlers 添加可空的 group_id 外键列

兼容性说明
- SQLite 下使用 batch 模式添加外键；若目标已存在则跳过，保证幂等。
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f2a0c4b9e3a"
down_revision = "364081709abf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    existing_tables = set(inspector.get_table_names())

    # 1) 创建 crawler_groups 表（如不存在）
    if "crawler_groups" not in existing_tables:
        op.create_table(
            "crawler_groups",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False, index=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("color", sa.String(length=16), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.UniqueConstraint("user_id", "slug", name="uq_crawler_groups_user_slug"),
        )
        op.create_index("ix_crawler_groups_slug", "crawler_groups", ["slug"])  # 与模型一致

    # 2) 为 api_keys 添加 group_id（如缺失）
    api_keys_columns = {c["name"] for c in inspector.get_columns("api_keys")}
    api_keys_fks = inspector.get_foreign_keys("api_keys")
    has_api_keys_fk = any(
        (fk.get("name") == "fk_api_keys_group_id" or fk.get("referred_table") == "crawler_groups")
        for fk in api_keys_fks
    )

    if dialect == "sqlite":
        with op.batch_alter_table("api_keys") as batch_op:
            if "group_id" not in api_keys_columns:
                batch_op.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
            if not has_api_keys_fk:
                batch_op.create_foreign_key(
                    "fk_api_keys_group_id",
                    "crawler_groups",
                    ["group_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
    else:
        if "group_id" not in api_keys_columns:
            op.add_column("api_keys", sa.Column("group_id", sa.Integer(), nullable=True))
        if not has_api_keys_fk:
            op.create_foreign_key(
                "fk_api_keys_group_id",
                "api_keys",
                "crawler_groups",
                ["group_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # 3) 为 crawlers 添加 group_id（如缺失）
    crawlers_columns = {c["name"] for c in inspector.get_columns("crawlers")}
    crawlers_fks = inspector.get_foreign_keys("crawlers")
    has_crawlers_fk = any(
        (fk.get("name") == "fk_crawlers_group_id" or fk.get("referred_table") == "crawler_groups")
        for fk in crawlers_fks
    )

    if dialect == "sqlite":
        with op.batch_alter_table("crawlers") as batch_op:
            if "group_id" not in crawlers_columns:
                batch_op.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
            if not has_crawlers_fk:
                batch_op.create_foreign_key(
                    "fk_crawlers_group_id",
                    "crawler_groups",
                    ["group_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
    else:
        if "group_id" not in crawlers_columns:
            op.add_column("crawlers", sa.Column("group_id", sa.Integer(), nullable=True))
        if not has_crawlers_fk:
            op.create_foreign_key(
                "fk_crawlers_group_id",
                "crawlers",
                "crawler_groups",
                ["group_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    # 尽量容错的降级逻辑
    if dialect == "sqlite":
        with op.batch_alter_table("crawlers") as batch_op:
            fks = {fk.get("name") for fk in inspector.get_foreign_keys("crawlers")}
            if "fk_crawlers_group_id" in fks:
                batch_op.drop_constraint("fk_crawlers_group_id", type_="foreignkey")
            cols = {c["name"] for c in inspector.get_columns("crawlers")}
            if "group_id" in cols:
                batch_op.drop_column("group_id")
        with op.batch_alter_table("api_keys") as batch_op:
            fks = {fk.get("name") for fk in inspector.get_foreign_keys("api_keys")}
            if "fk_api_keys_group_id" in fks:
                batch_op.drop_constraint("fk_api_keys_group_id", type_="foreignkey")
            cols = {c["name"] for c in inspector.get_columns("api_keys")}
            if "group_id" in cols:
                batch_op.drop_column("group_id")
    else:
        fks = {fk.get("name") for fk in inspector.get_foreign_keys("crawlers")}
        if "fk_crawlers_group_id" in fks:
            op.drop_constraint("fk_crawlers_group_id", "crawlers", type_="foreignkey")
        cols = {c["name"] for c in inspector.get_columns("crawlers")}
        if "group_id" in cols:
            op.drop_column("crawlers", "group_id")

        fks = {fk.get("name") for fk in inspector.get_foreign_keys("api_keys")}
        if "fk_api_keys_group_id" in fks:
            op.drop_constraint("fk_api_keys_group_id", "api_keys", type_="foreignkey")
        cols = {c["name"] for c in inspector.get_columns("api_keys")}
        if "group_id" in cols:
            op.drop_column("api_keys", "group_id")

    tables = set(inspector.get_table_names())
    if "crawler_groups" in tables:
        # 先删除索引
        try:
            op.drop_index("ix_crawler_groups_slug", table_name="crawler_groups")
        except Exception:
            pass
        op.drop_table("crawler_groups")

