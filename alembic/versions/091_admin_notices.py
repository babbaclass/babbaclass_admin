"""Add admin_notices table

Revision ID: 091
Revises: 090
Create Date: 2026-06-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "091"
down_revision = "090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "admin_notices" in inspector.get_table_names():
        return
    op.create_table(
        "admin_notices",
        sa.Column("notice_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("visible_from", sa.Date(), nullable=False),
        sa.Column("visible_to", sa.Date(), nullable=False),
        sa.Column("is_exposed", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("notice_id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_index("ix_admin_notices_author_user_id", "admin_notices", ["author_user_id"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "admin_notices" not in inspector.get_table_names():
        return
    op.drop_index("ix_admin_notices_author_user_id", table_name="admin_notices")
    op.drop_table("admin_notices")
