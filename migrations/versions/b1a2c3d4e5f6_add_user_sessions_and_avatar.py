"""
新增用户头像字段与登录会话表（支持多设备 + 记住我）
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "b1a2c3d4e5f6"
down_revision = "f7d2a1c3d4e5"
branch_labels = None
migration_dependencies = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # users.avatar_url（若已存在则跳过）
    if insp.has_table("users"):
        try:
            user_cols = {c["name"] for c in insp.get_columns("users")}
        except Exception:
            user_cols = set()
        if "avatar_url" not in user_cols:
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(sa.Column("avatar_url", sa.String(length=255), nullable=True))

    # user_sessions 表及索引（若已存在则跳过/补齐索引）
    if not insp.has_table("user_sessions"):
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("remember_me", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_active_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ),
        )
        op.create_index("ix_user_sessions_session_id", "user_sessions", ["session_id"], unique=True)
        op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
        op.create_index("ix_user_sessions_revoked", "user_sessions", ["revoked"], unique=False)
    else:
        try:
            idx_names = {i.get("name") for i in insp.get_indexes("user_sessions")}
        except Exception:
            idx_names = set()
        if "ix_user_sessions_session_id" not in idx_names:
            op.create_index("ix_user_sessions_session_id", "user_sessions", ["session_id"], unique=True)
        if "ix_user_sessions_user_id" not in idx_names:
            op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
        if "ix_user_sessions_revoked" not in idx_names:
            op.create_index("ix_user_sessions_revoked", "user_sessions", ["revoked"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_sessions_revoked", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_session_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("avatar_url")
