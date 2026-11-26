"""Allow null contract_end_date for contract_endings table

Revision ID: 082
Revises: 081
Create Date: 2026-02-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "082"
down_revision = "081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "contract_endings",
        "contract_end_date",
        existing_type=sa.Date(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "contract_endings",
        "contract_end_date",
        existing_type=sa.Date(),
        nullable=False,
    )
