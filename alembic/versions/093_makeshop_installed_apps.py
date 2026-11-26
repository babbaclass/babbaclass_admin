"""Add makeshop_installed_apps table

Revision ID: 093
Revises: 092
Create Date: 2026-07-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "093"
down_revision = "092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "makeshop_installed_apps" in inspector.get_table_names():
        return
    op.create_table(
        "makeshop_installed_apps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_uid", sa.String(length=100), nullable=False),
        sa.Column("client_id", sa.String(length=100), nullable=True),
        sa.Column("app_name", sa.String(length=255), nullable=True),
        sa.Column("app_url", sa.String(length=500), nullable=True),
        sa.Column("action_type", sa.String(length=50), nullable=True),
        sa.Column("installed_at", sa.Date(), nullable=True),
        sa.Column("expired_at", sa.Date(), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_index("ix_makeshop_installed_apps_shop_uid", "makeshop_installed_apps", ["shop_uid"], unique=True)
    op.create_index("ix_makeshop_installed_apps_client_id", "makeshop_installed_apps", ["client_id"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "makeshop_installed_apps" not in inspector.get_table_names():
        return
    op.drop_index("ix_makeshop_installed_apps_client_id", table_name="makeshop_installed_apps")
    op.drop_index("ix_makeshop_installed_apps_shop_uid", table_name="makeshop_installed_apps")
    op.drop_table("makeshop_installed_apps")
