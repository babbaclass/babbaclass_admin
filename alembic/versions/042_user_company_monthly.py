"""042 Add user & company monthly aggregate tables

Revision ID: 042_user_company_monthly
Revises: 041
Create Date: 2025-11-24
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '042_user_company_monthly'
down_revision = '041'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    
    if 'settlement_user_monthly_aggregates' not in insp.get_table_names():
        op.create_table(
            'settlement_user_monthly_aggregates',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), nullable=False, index=True),
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
        op.create_index('ix_user_monthly_aggregate_period', 'settlement_user_monthly_aggregates', ['user_id','year','month'], unique=True)

    if 'settlement_company_monthly_aggregates' not in insp.get_table_names():
        op.create_table(
            'settlement_company_monthly_aggregates',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('company_id', sa.Integer(), nullable=False, index=True),
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
        op.create_index('ix_company_monthly_aggregate_period', 'settlement_company_monthly_aggregates', ['company_id','year','month'], unique=True)


def downgrade():
    op.drop_index('ix_company_monthly_aggregate_period', table_name='settlement_company_monthly_aggregates')
    op.drop_table('settlement_company_monthly_aggregates')
    op.drop_index('ix_user_monthly_aggregate_period', table_name='settlement_user_monthly_aggregates')
    op.drop_table('settlement_user_monthly_aggregates')
