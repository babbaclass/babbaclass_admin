"""Create contract_endings table for contract termination tracking

Revision ID: 081
Revises: 080
Create Date: 2026-02-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '081'
down_revision = '080'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'contract_endings',
        sa.Column('contract_end_id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.company_id'), nullable=False),
        sa.Column('contract_end_date', sa.Date(), nullable=False),
        sa.Column('total_payment_last_year', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_contract_endings_user_id', 'contract_endings', ['user_id'])
    op.create_index('ix_contract_endings_company_id', 'contract_endings', ['company_id'])
    op.create_index('ix_contract_endings_contract_end_date', 'contract_endings', ['contract_end_date'])
    op.create_index('ix_contract_endings_status', 'contract_endings', ['status'])


def downgrade() -> None:
    op.drop_index('ix_contract_endings_status', table_name='contract_endings')
    op.drop_index('ix_contract_endings_contract_end_date', table_name='contract_endings')
    op.drop_index('ix_contract_endings_company_id', table_name='contract_endings')
    op.drop_index('ix_contract_endings_user_id', table_name='contract_endings')
    op.drop_table('contract_endings')
