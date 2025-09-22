"""add group link support

为了兼容已经通过手工方式或线上补丁添加过列的数据库，此迁移脚本做了幂等处理：
- 仅在缺少列时才添加 `group_id`
- 在 SQLite 上，如果表已存在且仅添加外键会失败（不支持在线添加 FK），则跳过外键创建；
  若需要强一致外键，可在生产（非 SQLite）数据库执行，或使用 batch 重建表。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "87b1cbb7e6f7"
down_revision = "364081709abf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    columns = {c["name"] for c in inspector.get_columns("crawler_access_links")}
    fks = {fk.get("name") for fk in inspector.get_foreign_keys("crawler_access_links")}

    needs_add_column = "group_id" not in columns

    if dialect == "sqlite":
        # SQLite 不支持在线添加外键；使用 batch 在需要时一次性重建表
        if needs_add_column or ("fk_crawler_access_links_group_id" not in fks):
            with op.batch_alter_table("crawler_access_links") as batch_op:
                if needs_add_column:
                    batch_op.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
                # 仅当当前不存在该外键时尝试创建（SQLite 将在表重建时应用）
                if "fk_crawler_access_links_group_id" not in fks:
                    batch_op.create_foreign_key(
                        "fk_crawler_access_links_group_id",
                        "crawler_groups",
                        ["group_id"],
                        ["id"],
                        ondelete="SET NULL",
                    )
    else:
        if needs_add_column:
            op.add_column(
                "crawler_access_links",
                sa.Column("group_id", sa.Integer(), nullable=True),
            )
        if "fk_crawler_access_links_group_id" not in fks:
            op.create_foreign_key(
                "fk_crawler_access_links_group_id",
                "crawler_access_links",
                "crawler_groups",
                ["group_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    # 降级时尽量容错：若外键不存在或列不存在则跳过
    if dialect == "sqlite":
        with op.batch_alter_table("crawler_access_links") as batch_op:
            # SQLite 需要在 batch 下处理约束和列
            fks = {fk.get("name") for fk in inspector.get_foreign_keys("crawler_access_links")}
            if "fk_crawler_access_links_group_id" in fks:
                batch_op.drop_constraint(
                    "fk_crawler_access_links_group_id",
                    type_="foreignkey",
                )
            columns = {c["name"] for c in inspector.get_columns("crawler_access_links")}
            if "group_id" in columns:
                batch_op.drop_column("group_id")
    else:
        fks = {fk.get("name") for fk in inspector.get_foreign_keys("crawler_access_links")}
        if "fk_crawler_access_links_group_id" in fks:
            op.drop_constraint(
                "fk_crawler_access_links_group_id",
                "crawler_access_links",
                type_="foreignkey",
            )
        columns = {c["name"] for c in inspector.get_columns("crawler_access_links")}
        if "group_id" in columns:
            op.drop_column("crawler_access_links", "group_id")
