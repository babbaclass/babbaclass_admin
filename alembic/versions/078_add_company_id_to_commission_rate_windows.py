"""Add company_id back to commission_rate_windows

Revision ID: 078
Revises: 077
Create Date: 2026-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '078'
down_revision = '077'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add company_id column for branch-specific BASCLE overrides
    op.add_column('commission_rate_windows', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_index('ix_commission_rate_windows_company_id', 'commission_rate_windows', ['company_id'], unique=False)
    op.create_foreign_key(
        'fk_commission_rate_windows_company_id',
        'commission_rate_windows', 'companies',
        ['company_id'], ['company_id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_commission_rate_windows_company_id', 'commission_rate_windows', type_='foreignkey')
    op.drop_index('ix_commission_rate_windows_company_id', table_name='commission_rate_windows')
    op.drop_column('commission_rate_windows', 'company_id')
