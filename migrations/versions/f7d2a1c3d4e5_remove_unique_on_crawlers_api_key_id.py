"""
移除 crawlers.api_key_id 的唯一约束/索引（允许一个 API Key 绑定多个工程）

- 兼容 PostgreSQL / MySQL(MariaDB) / SQLite
- 注意：SQLite 若存在表级 UNIQUE 生成的 sqlite_autoindex，需要用“重建表”策略；
        本项目在 app/database.py 的启动升级已包含 SQLite 重建兜底逻辑。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7d2a1c3d4e5"
down_revision = None  # 若已有历史版本，请改为上一 revision id
branch_labels = None
migration_dependencies = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # 删除唯一约束（未知名）与唯一索引（若存在）
        # 采用 name[] 比较，避免 text[] 与 name[] 类型不匹配导致的错误
        op.execute(
            sa.text(
                """
DO $$
DECLARE r record;
BEGIN
  -- 删除仅包含 api_key_id 的唯一约束
  FOR r IN (
    SELECT c.conname AS name
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE t.relname = 'crawlers' AND c.contype = 'u'
      AND (
        SELECT array_agg(att.attname ORDER BY att.attnum)
        FROM unnest(c.conkey) AS colnum
        JOIN pg_attribute att ON att.attrelid = t.oid AND att.attnum = colnum
      ) = ARRAY['api_key_id']::name[]
  ) LOOP
    EXECUTE format('ALTER TABLE crawlers DROP CONSTRAINT %I', r.name);
  END LOOP;

  -- 删除包含 api_key_id 且唯一的索引（保险）
  FOR r IN (
    SELECT indexname AS name
    FROM pg_indexes
    WHERE tablename='crawlers' AND indexdef ILIKE '%UNIQUE%'
      AND indexdef ILIKE '%(api_key_id%'
  ) LOOP
    EXECUTE format('DROP INDEX IF EXISTS %I', r.name);
  END LOOP;
END $$;
                """
            )
        )
    elif dialect in ("mysql", "mariadb"):
        # 删除包含 api_key_id 的唯一索引（名称未知，遍历 information_schema）
        rows = bind.exec_driver_sql(
            """
SELECT INDEX_NAME
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'crawlers'
  AND NON_UNIQUE = 0
  AND COLUMN_NAME = 'api_key_id'
            """
        ).fetchall()
        for (idx_name,) in rows:
            try:
                op.execute(sa.text(f"ALTER TABLE crawlers DROP INDEX `{idx_name}`"))
            except Exception:
                pass
    elif dialect == "sqlite":
        # 删除显式唯一索引（若存在）；autoindex 无法直接删除，交由应用启动兜底处理
        rows = bind.exec_driver_sql("PRAGMA index_list('crawlers')").fetchall()
        for row in rows:
            try:
                name = row[1]
                unique = bool(row[2])
            except Exception:
                name = row["name"]
                unique = bool(row["unique"])
            if not unique:
                continue
            info = bind.exec_driver_sql(f"PRAGMA index_info('{name}')").fetchall()
            cols = [c[2] if len(c) >= 3 else c["name"] for c in info]
            if cols == ["api_key_id"] and not str(name).startswith("sqlite_autoindex_"):
                op.execute(sa.text(f"DROP INDEX IF EXISTS '{name}'"))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 警告：降级会恢复“api_key_id 唯一”，与当前业务不再匹配，仅为可逆性保留
    if dialect == "postgresql":
        op.execute(sa.text("ALTER TABLE crawlers ADD CONSTRAINT uq_crawlers_api_key_id UNIQUE (api_key_id)"))
    elif dialect in ("mysql", "mariadb"):
        op.execute(sa.text("ALTER TABLE crawlers ADD UNIQUE KEY uq_crawlers_api_key_id (api_key_id)"))
    elif dialect == "sqlite":
        op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_crawlers_api_key_id ON crawlers(api_key_id)"))
