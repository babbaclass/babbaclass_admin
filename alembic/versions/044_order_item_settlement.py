"""Add order item settlement tables

Revision ID: 044_order_item_settlement
Revises: 043_settlement_monthly_check
Create Date: 2025-11-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '044_order_item_settlement'
down_revision = '043_settlement_monthly_check'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create settlement_order_items table
    op.create_table(
        'settlement_order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('ordernum', sa.String(100), nullable=False),
        sa.Column('product_uid', sa.String(100), nullable=False),
        sa.Column('product_name', sa.String(255), nullable=False),
        sa.Column('order_date', sa.String(20), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_price', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id']),
        sa.ForeignKeyConstraint(['product_uid'], ['products.uid']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_settlement_order_items_user_id', 'settlement_order_items', ['user_id'])
    op.create_index('ix_settlement_order_items_company_id', 'settlement_order_items', ['company_id'])
    op.create_index('ix_settlement_order_items_ordernum', 'settlement_order_items', ['ordernum'])
    op.create_index('ix_settlement_order_items_year_month', 'settlement_order_items', ['year', 'month'])

    # Create settlement_user_order_item_monthly_aggregates table
    op.create_table(
        'settlement_user_order_item_monthly_aggregates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_uid', sa.String(100), nullable=False),
        sa.Column('product_name', sa.String(255), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('total_orders', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['product_uid'], ['products.uid']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_settlement_user_order_item_monthly_aggregates_user_id', 'settlement_user_order_item_monthly_aggregates', ['user_id'])
    op.create_index('ix_settlement_user_order_item_monthly_aggregates_year_month', 'settlement_user_order_item_monthly_aggregates', ['year', 'month'])

    # Create settlement_company_order_item_monthly_aggregates table
    op.create_table(
        'settlement_company_order_item_monthly_aggregates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('product_uid', sa.String(100), nullable=False),
        sa.Column('product_name', sa.String(255), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('total_orders', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id']),
        sa.ForeignKeyConstraint(['product_uid'], ['products.uid']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_settlement_company_order_item_monthly_aggregates_company_id', 'settlement_company_order_item_monthly_aggregates', ['company_id'])
    op.create_index('ix_settlement_company_order_item_monthly_aggregates_year_month', 'settlement_company_order_item_monthly_aggregates', ['year', 'month'])


def downgrade() -> None:
    op.drop_index('ix_settlement_company_order_item_monthly_aggregates_year_month', table_name='settlement_company_order_item_monthly_aggregates')
    op.drop_index('ix_settlement_company_order_item_monthly_aggregates_company_id', table_name='settlement_company_order_item_monthly_aggregates')
    op.drop_table('settlement_company_order_item_monthly_aggregates')
    
    op.drop_index('ix_settlement_user_order_item_monthly_aggregates_year_month', table_name='settlement_user_order_item_monthly_aggregates')
    op.drop_index('ix_settlement_user_order_item_monthly_aggregates_user_id', table_name='settlement_user_order_item_monthly_aggregates')
    op.drop_table('settlement_user_order_item_monthly_aggregates')
    
    op.drop_index('ix_settlement_order_items_year_month', table_name='settlement_order_items')
    op.drop_index('ix_settlement_order_items_ordernum', table_name='settlement_order_items')
    op.drop_index('ix_settlement_order_items_company_id', table_name='settlement_order_items')
    op.drop_index('ix_settlement_order_items_user_id', table_name='settlement_order_items')
    op.drop_table('settlement_order_items')
