"""add config templates and alert tables"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d3a4b1f6e781"
down_revision = "87b1cbb7e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crawler_config_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("format", sa.String(length=16), nullable=False, server_default="json"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_crawler_config_template_name"),
    )

    op.create_table(
        "crawler_config_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("format", sa.String(length=16), nullable=False, server_default="json"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("crawler_config_templates.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("user_id", "target_type", "target_id", name="uq_crawler_config_assignment_target"),
    )

    op.create_table(
        "crawler_alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False, server_default="all"),
        sa.Column("target_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("payload_field", sa.String(length=128), nullable=True),
        sa.Column("comparator", sa.String(length=8), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("status_from", sa.String(length=16), nullable=True),
        sa.Column("status_to", sa.String(length=16), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("channels", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_crawler_alert_rule_name"),
    )

    op.create_table(
        "crawler_alert_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("crawler_alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crawler_id", sa.Integer(), sa.ForeignKey("crawlers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consecutive_hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_value", sa.Float(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False, server_default='{}'),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("rule_id", "crawler_id", name="uq_crawler_alert_state"),
    )

    op.create_table(
        "crawler_alert_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("crawler_alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crawler_id", sa.Integer(), sa.ForeignKey("crawlers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default='{}'),
        sa.Column("channel_results", sa.JSON(), nullable=False, server_default='[]'),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_crawler_alert_events_triggered_at", "crawler_alert_events", ["triggered_at"])


def downgrade() -> None:
    op.drop_index("ix_crawler_alert_events_triggered_at", table_name="crawler_alert_events")
    op.drop_table("crawler_alert_events")
    op.drop_table("crawler_alert_states")
    op.drop_table("crawler_alert_rules")
    op.drop_table("crawler_config_assignments")
    op.drop_table("crawler_config_templates")
