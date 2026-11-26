"""Add unique constraint on settlements identity key

Revision ID: 092
Revises: 091
Create Date: 2026-07-13 14:40:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "092"
down_revision = "091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user + company + type + date 조합은 1건만 허용 (monthly/mtd 중복 insert 방지)
    op.create_unique_constraint(
        "uq_settlements_user_company_type_date",
        "settlements",
        ["user_id", "company_id", "settlement_type", "settlement_date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_settlements_user_company_type_date",
        "settlements",
        type_="unique",
    )
