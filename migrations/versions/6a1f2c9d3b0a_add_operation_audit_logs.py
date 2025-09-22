"""add operation audit logs table

Revision ID: 6a1f2c9d3b0a
Revises: d3a4b1f6e781
Create Date: 2025-09-22 00:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6a1f2c9d3b0a"
down_revision = "d3a4b1f6e781"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True, index=True),
        sa.Column("target_name", sa.String(length=128), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("actor_name", sa.String(length=128), nullable=True),
        sa.Column("actor_ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_operation_audit_logs_created_at", "operation_audit_logs", ["created_at"]) 


def downgrade() -> None:
    op.drop_index("ix_operation_audit_logs_created_at", table_name="operation_audit_logs")
    op.drop_table("operation_audit_logs")

