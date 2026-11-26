"""Add renewal_count to contract_end table

Revision ID: 085
Revises: 084
Create Date: 2026-03-15 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '085'
down_revision = '084'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'contract_end',
        sa.Column('renewal_count', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('contract_end', 'renewal_count')
