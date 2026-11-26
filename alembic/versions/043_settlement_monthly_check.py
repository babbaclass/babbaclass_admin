"""043 Ensure settlement_monthly_aggregates table exists (replaces orphan branch)

Revision ID: 043_settlement_monthly_check
Revises: 042_user_company_monthly
Create Date: 2025-11-24
"""
from alembic import op
import sqlalchemy as sa

revision = '043_settlement_monthly_check'
down_revision = '042_user_company_monthly'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'settlement_monthly_aggregates' not in insp.get_table_names():
        op.create_table(
            'settlement_monthly_aggregates',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(), nullable=False, index=True),
            sa.Column('role_id', sa.Integer(), nullable=False, index=True),
            sa.Column('year', sa.Integer(), nullable=False, index=True),
            sa.Column('month', sa.Integer(), nullable=False, index=True),
            sa.Column('total_orders', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_items', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_amount', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_commission', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('deducted_tax', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('deducted_local_tax', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('net_settlement_amount', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index(
            'ix_settlement_monthly_company_role_period',
            'settlement_monthly_aggregates',
            ['company_id','role_id','year','month'],
            unique=True
        )


def downgrade():
    # Safe downgrade: drop table if exists
    op.drop_index('ix_settlement_monthly_company_role_period', table_name='settlement_monthly_aggregates')
    op.drop_table('settlement_monthly_aggregates')
