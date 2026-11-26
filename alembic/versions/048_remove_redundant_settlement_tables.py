"""remove redundant settlement tables

Revision ID: 048
Revises: 047
Create Date: 2025-11-26

정산 테이블 구조 정리:
- 중복 테이블 제거: SettlementMonthlyAggregate, SettlementUserMonthlyAggregate
- 판매 통계 테이블 제거: SettlementOrderItem, SettlementUserOrderItemMonthlyAggregate, SettlementCompanyOrderItemMonthlyAggregate
- Order/OrderItem 테이블에서 직접 조회하도록 변경
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '048'
down_revision = '047'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    중복 및 불필요한 정산 테이블 제거
    """
    # 1. SettlementOrderItem 관련 테이블 제거 (Order/OrderItem에서 직접 조회)
    op.drop_table('settlement_company_order_item_monthly_aggregates')
    op.drop_table('settlement_user_order_item_monthly_aggregates')
    op.drop_table('settlement_order_items')
    
    # 2. 중복 정산 집계 테이블 제거
    op.drop_table('settlement_user_monthly_aggregates')  # Settlement로 대체
    op.drop_table('settlement_monthly_aggregates')  # SettlementCompanyMonthlyAggregate로 통합


def downgrade() -> None:
    """
    제거한 테이블 복원
    """
    # SettlementMonthlyAggregate 복원
    op.create_table('settlement_monthly_aggregates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('total_orders', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_items', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_amount', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_commission', sa.Integer(), server_default='0', nullable=True),
        sa.Column('deducted_tax', sa.Integer(), server_default='0', nullable=True),
        sa.Column('deducted_local_tax', sa.Integer(), server_default='0', nullable=True),
        sa.Column('net_settlement_amount', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['roles.role_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settlement_monthly_aggregates_company_id'), 'settlement_monthly_aggregates', ['company_id'], unique=False)
    op.create_index(op.f('ix_settlement_monthly_aggregates_month'), 'settlement_monthly_aggregates', ['month'], unique=False)
    op.create_index(op.f('ix_settlement_monthly_aggregates_role_id'), 'settlement_monthly_aggregates', ['role_id'], unique=False)
    op.create_index(op.f('ix_settlement_monthly_aggregates_year'), 'settlement_monthly_aggregates', ['year'], unique=False)
    
    # SettlementUserMonthlyAggregate 복원
    op.create_table('settlement_user_monthly_aggregates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('total_orders', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_items', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_amount', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_commission', sa.Integer(), server_default='0', nullable=True),
        sa.Column('deducted_tax', sa.Integer(), server_default='0', nullable=True),
        sa.Column('deducted_local_tax', sa.Integer(), server_default='0', nullable=True),
        sa.Column('net_settlement_amount', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settlement_user_monthly_aggregates_month'), 'settlement_user_monthly_aggregates', ['month'], unique=False)
    op.create_index(op.f('ix_settlement_user_monthly_aggregates_user_id'), 'settlement_user_monthly_aggregates', ['user_id'], unique=False)
    op.create_index(op.f('ix_settlement_user_monthly_aggregates_year'), 'settlement_user_monthly_aggregates', ['year'], unique=False)
    
    # SettlementOrderItem 복원
    op.create_table('settlement_order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('ordernum', sa.String(length=100), nullable=False),
        sa.Column('product_uid', sa.String(length=100), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('order_date', sa.String(length=20), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=True),
        sa.Column('unit_price', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_price', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id'], ),
        sa.ForeignKeyConstraint(['product_uid'], ['products.uid'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settlement_order_items_month'), 'settlement_order_items', ['month'], unique=False)
    op.create_index(op.f('ix_settlement_order_items_ordernum'), 'settlement_order_items', ['ordernum'], unique=False)
    op.create_index(op.f('ix_settlement_order_items_year'), 'settlement_order_items', ['year'], unique=False)
    
    # SettlementUserOrderItemMonthlyAggregate 복원
    op.create_table('settlement_user_order_item_monthly_aggregates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_uid', sa.String(length=100), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('total_orders', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_quantity', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_amount', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['product_uid'], ['products.uid'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settlement_user_order_item_monthly_aggregates_month'), 'settlement_user_order_item_monthly_aggregates', ['month'], unique=False)
    op.create_index(op.f('ix_settlement_user_order_item_monthly_aggregates_product_uid'), 'settlement_user_order_item_monthly_aggregates', ['product_uid'], unique=False)
    op.create_index(op.f('ix_settlement_user_order_item_monthly_aggregates_user_id'), 'settlement_user_order_item_monthly_aggregates', ['user_id'], unique=False)
    op.create_index(op.f('ix_settlement_user_order_item_monthly_aggregates_year'), 'settlement_user_order_item_monthly_aggregates', ['year'], unique=False)
    
    # SettlementCompanyOrderItemMonthlyAggregate 복원
    op.create_table('settlement_company_order_item_monthly_aggregates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('product_uid', sa.String(length=100), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('total_orders', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_quantity', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_amount', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id'], ),
        sa.ForeignKeyConstraint(['product_uid'], ['products.uid'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settlement_company_order_item_monthly_aggregates_company_id'), 'settlement_company_order_item_monthly_aggregates', ['company_id'], unique=False)
    op.create_index(op.f('ix_settlement_company_order_item_monthly_aggregates_month'), 'settlement_company_order_item_monthly_aggregates', ['month'], unique=False)
    op.create_index(op.f('ix_settlement_company_order_item_monthly_aggregates_product_uid'), 'settlement_company_order_item_monthly_aggregates', ['product_uid'], unique=False)
    op.create_index(op.f('ix_settlement_company_order_item_monthly_aggregates_year'), 'settlement_company_order_item_monthly_aggregates', ['year'], unique=False)
