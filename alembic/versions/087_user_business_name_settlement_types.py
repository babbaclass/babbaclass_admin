"""Add business_name and settlement type flags to users

Revision ID: 087
Revises: 086
Create Date: 2026-05-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "087"
down_revision = "086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    if "business_name" not in columns:
        op.add_column("users", sa.Column("business_name", sa.String(255), nullable=True))
    if "settlement_personal" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "settlement_personal",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            ),
        )
    if "settlement_business" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "settlement_business",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    if "settlement_business" in columns:
        op.drop_column("users", "settlement_business")
    if "settlement_personal" in columns:
        op.drop_column("users", "settlement_personal")
    if "business_name" in columns:
        op.drop_column("users", "business_name")
