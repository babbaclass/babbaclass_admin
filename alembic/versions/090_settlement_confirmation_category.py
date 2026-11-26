"""Add confirmation_category to settlement_statement_confirmations

Revision ID: 090
Revises: 089
Create Date: 2026-06-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "090"
down_revision = "089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "settlement_statement_confirmations" not in inspector.get_table_names():
        return
    columns = {
        col["name"] for col in inspector.get_columns("settlement_statement_confirmations")
    }
    if "confirmation_category" not in columns:
        op.add_column(
            "settlement_statement_confirmations",
            sa.Column("confirmation_category", sa.String(length=10), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "settlement_statement_confirmations" not in inspector.get_table_names():
        return
    columns = {
        col["name"] for col in inspector.get_columns("settlement_statement_confirmations")
    }
    if "confirmation_category" in columns:
        op.drop_column("settlement_statement_confirmations", "confirmation_category")
